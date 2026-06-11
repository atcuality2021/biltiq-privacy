# SPDX-License-Identifier: MIT
"""Public anonymisation facade — detect, pseudonymise, generalise, attest, chain.

Ports the text-pipeline orchestration of CDSCO-RegAI's
``backend/modules/anonymisation/pipeline.py`` (BILTIQ-012). Only the
orchestration travels: the PDF extractor, the LLM contextual-detection branch,
and the CSV helper stay behind in the source project (extraction is the
caller's concern; LLM detection arrives Phase D via an injected
:class:`~biltiq_privacy.detectors.base.Detector`).

The single piece of ported *logic* is :func:`_merge_detections` — everything
else is composition over already-shipped modules (BILTIQ-007/008/009/010/011).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from biltiq_privacy.core.audit_chain import (
    GENESIS_PREV_HASH,
    ChainedRow,
    JsonValue,
    append_row,
)
from biltiq_privacy.core.doc_hasher import hash_text
from biltiq_privacy.core.generaliser import GeneralisationSpan, generalise_text
from biltiq_privacy.core.pseudonymiser import AuditRecord, Detection, Pseudonymiser
from biltiq_privacy.detectors.base import DetectedEntity, Detector
from biltiq_privacy.regimes.base import ComplianceReport, Regime


@dataclass(slots=True, frozen=True)
class AnonymiseResult:
    """Everything one :func:`anonymise` call produced.

    ``detections`` necessarily carry the original span text (the detector
    contract) — treat the result as sensitive and do not log it raw.
    The original input text is deliberately *not* echoed back (the caller
    already holds it; echoing widens the PII surface).
    """

    anonymised_text: str
    """Final output: pseudonymised, then generalised when requested."""

    detections: tuple[DetectedEntity, ...]
    """Merged, start-ordered, non-overlapping spans."""

    audit_records: tuple[AuditRecord, ...]
    """One per replaced span, document order — aligned 1:1 with ``detections``."""

    audit_row: ChainedRow
    """The appended hash-chain link; ``audit_row["hash"]`` feeds the next
    call's ``prev_hash``. The payload carries counts, flags, and SHA-256
    commitments only — never values, tokens, or positions."""

    compliance: ComplianceReport | None
    """``None`` unless a ``regime`` was passed."""


def _merge_detections(detections: list[DetectedEntity]) -> list[DetectedEntity]:
    """Deduplicate overlapping spans; on overlap the higher score wins.

    Ported verbatim from CDSCO ``pipeline.py::_merge_detections`` over a
    single pre-concatenated list: sort by ``(start, -score)``, then a single
    pass where a span overlapping the previous kept span replaces it only if
    its score is strictly higher. Output is start-ordered and
    non-overlapping — the ordering contract the facade's
    detections↔audit-records zip alignment depends on.

    Intentionally different from BILTIQ-015's planned ``CompositeDetector``
    (longest-span-wins): that policy composes *across backends*; this one
    deduplicates *within one merged result*. Do not harmonise them.
    """
    ordered = sorted(detections, key=lambda d: (d["start"], -d["score"]))

    merged: list[DetectedEntity] = []
    for det in ordered:
        if merged and det["start"] < merged[-1]["end"]:
            # Overlap — keep higher confidence
            if det["score"] > merged[-1]["score"]:
                merged[-1] = det
            continue
        merged.append(det)
    return merged


def _build_audit_payload(
    *,
    generated_at: str,
    original: str,
    anonymised: str,
    detections: list[DetectedEntity],
    generalised: bool,
    regime: Regime | None,
    compliance: ComplianceReport | None,
) -> dict[str, JsonValue]:
    """Assemble the PII-free chain payload.

    Counts, flags, and SHA-256 commitments only — never original values,
    never pseudonym tokens, never span positions. The two hashes bind the row
    to a specific input/output pair: an auditor holding the documents can
    re-derive and verify; the chain alone reveals nothing.
    """
    entity_summary: dict[str, JsonValue] = {}
    for det in detections:
        current = entity_summary.get(det["entity_type"], 0)
        # current is always an int here (this loop is the only writer); the
        # isinstance guard narrows JsonValue for mypy --strict without a cast.
        entity_summary[det["entity_type"]] = (
            current if isinstance(current, int) else 0
        ) + 1

    return {
        "generated_at": generated_at,
        "doc_hash": hash_text(original),
        "anonymised_hash": hash_text(anonymised),
        "entities_detected": len(detections),
        "entity_summary": entity_summary,
        "generalised": generalised,
        "regime_id": regime.regime_id if regime is not None else None,
        "compliant": compliance.compliant if compliance is not None else None,
    }


def anonymise(
    text: str,
    *,
    detector: Detector,
    key: bytes | str,
    generated_at: str,
    regime: Regime | None = None,
    generalise: bool = True,
    prev_hash: str = GENESIS_PREV_HASH,
) -> AnonymiseResult:
    """Anonymise ``text`` end to end and append a tamper-evident audit row.

    Chains the shipped pipeline pieces:
    ``detector.detect`` → :func:`_merge_detections` →
    :meth:`~biltiq_privacy.core.pseudonymiser.Pseudonymiser.pseudonymise_text`
    → :func:`~biltiq_privacy.core.generaliser.generalise_text` (skipped when
    ``generalise=False`` — CDSCO's ``pseudonymise_only`` mode) →
    ``regime.validate`` (only when a ``regime`` is given) →
    :func:`~biltiq_privacy.core.audit_chain.append_row`.

    Determinism contract: the library reads no clock and no environment.
    ``generated_at`` is caller-supplied and echoed verbatim into the payload;
    ``prev_hash`` continues an existing chain (default starts a new one at
    :data:`~biltiq_privacy.core.audit_chain.GENESIS_PREV_HASH`). Identical
    inputs therefore produce identical results, including the row hash.

    Empty / whitespace-only ``text`` skips only the detector call (no model
    load); the audit row is still appended — "document processed, no PII
    detected" is itself a compliance-relevant attestation, distinct from
    "document never processed".

    Note: a regime may legitimately report non-compliant over
    ``generalise=False`` output (e.g. DPDP-4 checks for generalisation
    markers) — the report attests whatever the pipeline produced.

    Raises:
        HMACKeyRequiredError: if ``key`` normalises to empty bytes —
            validated first, before any text is processed.
        MissingNERModelError: propagated from :class:`PresidioDetector`
            when the NER model is unavailable.
    """
    pseudonymiser = Pseudonymiser(key=key)  # fail-fast key validation

    detections: list[DetectedEntity] = []
    if text.strip():
        detections = _merge_detections(detector.detect(text))

    # Safe narrowing: DetectedEntity extends Detection (extra ``source`` key)
    # and pseudonymise_text only reads from the list; cast avoids a copy that
    # list-invariance would otherwise force under mypy --strict.
    pseudo_text, audit_records = pseudonymiser.pseudonymise_text(
        text, cast("list[Detection]", detections)
    )

    if generalise:
        # _merge_detections emits start-ordered spans and pseudonymise_text
        # returns audit records restored to document order, so this zip is
        # 1:1-aligned (test-pinned with out-of-order detector input).
        spans = [
            GeneralisationSpan(
                entity_type=det["entity_type"],
                text=det["text"],
                pseudonym_token=record["pseudonym_token"],
            )
            # strict=True turns a broken 1:1 ordering contract into a loud
            # ValueError instead of a silently mispaired token.
            for det, record in zip(detections, audit_records, strict=True)
        ]
        anonymised_text = generalise_text(pseudo_text, spans)
    else:
        anonymised_text = pseudo_text

    compliance: ComplianceReport | None = None
    if regime is not None:
        compliance = regime.validate(
            text,
            anonymised_text,
            detections,
            audit_records,
            generated_at=generated_at,
        )

    audit_row = append_row(
        prev_hash,
        _build_audit_payload(
            generated_at=generated_at,
            original=text,
            anonymised=anonymised_text,
            detections=detections,
            generalised=generalise,
            regime=regime,
            compliance=compliance,
        ),
    )

    return AnonymiseResult(
        anonymised_text=anonymised_text,
        detections=tuple(detections),
        audit_records=tuple(audit_records),
        audit_row=audit_row,
        compliance=compliance,
    )
