# SPDX-License-Identifier: MIT
"""The DPDP 2023 regime: CDSCO-RegAI's eight compliance checks behind ``Regime``.

Ports ``backend/compliance/dpdp_validator.py`` (151 LOC) minus its framework
glue. The residual-PII scan reuses the eight compiled BILTIQ-002 patterns by
reference and adds only the one pattern BILTIQ-002 lacks (EMAIL, ported
verbatim) — no regex is re-declared (spec AC3).

Four documented behaviour deltas vs the source, each pinned by a test in
``tests/regimes/test_dpdp.py`` (spec § Open Questions, all dev-ruled):

(a) **stricter scan** — nine residual types instead of the source's five;
    leaked GSTIN / Voter ID / IFSC / Medical-Reg values now fail DPDP-1.
(b) **phone boundary** — BILTIQ-002's ``PHONE_IN_PATTERN`` uses ``\\b`` where
    the source used an underscore-permitting lookbehind, so phones adjacent
    to underscores (``patient_98765…pdf`` filenames) match differently.
(c) **no PII values in the report by default** — DPDP-1 evidence carries
    ``"TYPE@position"`` locators; matched values are appended only on the
    explicit ``include_values=True`` opt-in, and evidence is capped at five
    entries (the source's ``real_residual[:5]``).
(d) **wider mask filter** — a residual match is skipped when its value
    contains *any* configured generalisation marker, not only ``"XXXX"``.
    With the default trio a leaked value containing a descriptive marker
    (e.g. an email containing ``"India"``) is filtered where the source
    would flag it; pass ``generalisation_markers=("XXXX",)`` for
    source-strict filtering.

The regime reads no clock, no environment, performs no I/O and no logging;
``generated_at`` is caller-supplied (BILTIQ-010 determinism precedent).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import ClassVar, Final

from biltiq_privacy.core.pseudonymiser import AuditRecord, Detection
from biltiq_privacy.indian.patterns import PATTERNS
from biltiq_privacy.regimes.base import ComplianceCheck, ComplianceReport, Regime

EMAIL_PATTERN: Final[str] = r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"
"""Ported verbatim from CDSCO ``pii_patterns.py`` — the one pattern BILTIQ-002
lacks. Lives here (not ``indian/patterns.py``) because email is not an Indian
ID format and the residual scan is its only consumer (design § Alternatives)."""

_RESIDUAL_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    **PATTERNS,
    "EMAIL": re.compile(EMAIL_PATTERN),
}

_DEFAULT_MARKERS: Final[tuple[str, ...]] = ("XXXX", "Healthcare Facility", "India")

_EVIDENCE_CAP: Final[int] = 5
"""The source's ``real_residual[:5]`` evidence truncation, ported."""


def _scan_residual_pii(text: str) -> list[tuple[str, int, str]]:
    """Scan for PII that may have leaked through anonymisation.

    Returns ``(type, position, value)`` triples. The value is needed by the
    caller's marker filter (and the ``include_values`` opt-in); it never
    reaches a report otherwise. Both token-skip heuristics are ported
    verbatim from the source: a match directly preceded by ``_`` or sitting
    inside an unclosed ``[`` bracket is part of a pseudonym token such as
    ``[IN_AADHAAR_1a2b3c4d]``, not a leak.
    """
    found: list[tuple[str, int, str]] = []
    for pii_type, pattern in _RESIDUAL_PATTERNS.items():
        for m in pattern.finditer(text):
            if text[max(0, m.start() - 1): m.start()] == "_":
                continue
            before = text[max(0, m.start() - 20): m.start()]
            if "[" in before and "]" not in before:
                continue
            found.append((pii_type, m.start(), m.group()))
    return found


class DPDPRegime(Regime):
    """DPDP Act 2023 attestation (plus NDHM / ICMR framework checks).

    ``generalisation_markers`` is the regime's single notion of "what
    generalised output looks like": it drives both the DPDP-4 generalisation
    check and the DPDP-1 residual mask filter (delta (d) — see the module
    docstring for the false-negative trade-off and the source-strict
    override).

    ``include_values=True`` appends the matched text to each DPDP-1 evidence
    locator (``"AADHAAR@112:…"``). **The report then contains PII** — enable
    it only when every report sink is access-controlled; the default emits
    locators only and is always safe to persist, log, or serve.
    """

    regime_id: ClassVar[str] = "DPDP-2023"
    frameworks: ClassVar[tuple[str, ...]] = ("DPDP Act 2023", "NDHM", "ICMR", "CDSCO")

    def __init__(
        self,
        *,
        generalisation_markers: tuple[str, ...] = _DEFAULT_MARKERS,
        include_values: bool = False,
    ) -> None:
        self._markers = generalisation_markers
        self._include_values = include_values

    def validate(
        self,
        original: str,
        anonymised: str,
        detections: Sequence[Detection],
        audit_records: Sequence[AuditRecord],
        *,
        generated_at: str,
    ) -> ComplianceReport:
        """Run the 8 CDSCO checks (DPDP-1..6, NDHM-1, ICMR-1) in source order.

        Assembled in plan Step 3; DPDP-1 lands first (Step 2) because it
        carries all four behaviour deltas.
        """
        raise NotImplementedError("assembled in BILTIQ-011 plan Step 3")

    def _check_pii_removal(self, anonymised: str) -> ComplianceCheck:
        """DPDP-1 — no detected-PII shape may survive in the output."""
        residual = [
            (pii_type, position, value)
            for pii_type, position, value in _scan_residual_pii(anonymised)
            if not any(marker in value for marker in self._markers)
        ]
        evidence = tuple(
            f"{pii_type}@{position}:{value}" if self._include_values else f"{pii_type}@{position}"
            for pii_type, position, value in residual[:_EVIDENCE_CAP]
        )
        return ComplianceCheck(
            check_id="DPDP-1",
            name="PII Removal Completeness",
            description="All detected PII must be removed or replaced in output",
            status="fail" if residual else "pass",
            details=f"{len(residual)} residual PII found" if residual else "No PII leaked",
            section="Section 8(1) — Data Minimisation",
            evidence=evidence,
        )
