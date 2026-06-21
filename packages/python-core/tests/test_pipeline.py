# SPDX-License-Identifier: MIT
"""Unit tests for the anonymise() facade (BILTIQ-012).

All tests run against an in-test fake detector — no Presidio/spaCy load.
The _merge_detections characterisation tests pin the CDSCO algorithm
(sort ``(start, -score)``; overlap keeps the strictly higher score).
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from biltiq_privacy.core.audit_chain import GENESIS_PREV_HASH, verify_chain
from biltiq_privacy.core.exceptions import HMACKeyRequiredError
from biltiq_privacy.detectors.base import DetectedEntity, Detector
from biltiq_privacy.pipeline import AnonymiseResult, _merge_detections, anonymise
from biltiq_privacy.regimes.base import ComplianceReport
from biltiq_privacy.regimes.dpdp import DPDPRegime

_KEY = b"unit-test-key-32-bytes-long!!!!!"
_TS = "2026-06-11T00:00:00+00:00"


class FakeDetector(Detector):
    """Returns a canned detection list — no model, no I/O."""

    def __init__(self, detections: list[DetectedEntity]) -> None:
        self._detections = detections

    def detect(
        self, text: str, language: str = "en"
    ) -> list[DetectedEntity]:
        return list(self._detections)


def _entity(
    entity_type: str,
    text: str,
    start: int,
    end: int,
    score: float,
    source: str = "test",
) -> DetectedEntity:
    return DetectedEntity(
        entity_type=entity_type,
        text=text,
        start=start,
        end=end,
        score=score,
        source=source,
    )


class TestMergeDetections:
    def test_merge_overlap_keeps_higher_score(self) -> None:
        """AC1 — CDSCO policy: overlapping span with higher score replaces."""
        low = _entity("IN_PHONE", "9876543210", start=10, end=20, score=0.5)
        high = _entity("IN_AADHAAR", "9876 5432 10", start=12, end=24, score=0.9)
        merged = _merge_detections([low, high])
        assert merged == [high]

    def test_merge_sorts_by_start_then_score_desc(self) -> None:
        """AC1 — output is start-ordered even from unordered input; equal-start
        ties favour the higher score (the lower-scored duplicate is dropped as
        an overlap, never promoted)."""
        late = _entity("EMAIL", "a@b.in", start=50, end=56, score=0.8)
        early_low = _entity("IN_PAN", "ABCDE1234F", start=5, end=15, score=0.4)
        early_high = _entity("IN_PAN", "ABCDE1234F", start=5, end=15, score=0.9)
        merged = _merge_detections([late, early_low, early_high])
        assert merged == [early_high, late]

    def test_merge_non_overlapping_pass_through(self) -> None:
        """AC1 — disjoint spans survive untouched, in start order."""
        first = _entity("IN_AADHAAR", "1234 5678 9012", start=0, end=14, score=0.9)
        second = _entity("IN_PHONE", "9876543210", start=20, end=30, score=0.7)
        merged = _merge_detections([second, first])
        assert merged == [first, second]


_TEXT = "Call Ravi on 9876543210 about PAN ABCDE1234F today."
_PHONE = _entity("IN_PHONE", "9876543210", start=13, end=23, score=0.85)
_PAN = _entity("IN_PAN", "ABCDE1234F", start=34, end=44, score=0.9)


def _run(
    text: str = _TEXT,
    detections: list[DetectedEntity] | None = None,
    **kwargs: object,
) -> AnonymiseResult:
    dets = [_PHONE, _PAN] if detections is None else detections
    return anonymise(
        text,
        detector=FakeDetector(dets),
        key=_KEY,
        generated_at=_TS,
        **kwargs,  # type: ignore[arg-type]  # test helper fans kwargs through verbatim
    )


class TestAnonymise:
    def test_anonymise_returns_frozen_slots_dataclass(self) -> None:
        """AC1 — result shape per the approved-versions mandate."""
        result = _run()
        assert dataclasses.is_dataclass(result)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.anonymised_text = "tampered"  # type: ignore[misc]  # the failure IS the assertion
        assert not hasattr(result, "__dict__")  # slots=True

    def test_anonymise_chains_detect_pseudonymise_generalise(self) -> None:
        """AC1 — happy path: originals gone, generalisations present."""
        result = _run()
        assert "9876543210" not in result.anonymised_text
        assert "ABCDE1234F" not in result.anonymised_text
        assert "+91 XXXXX XX210" in result.anonymised_text  # generalise_phone
        assert len(result.detections) == 2
        assert len(result.audit_records) == 2

    def test_generalise_false_skips_generaliser(self) -> None:
        """AC1 — pseudonymise-only mode keeps the HMAC tokens in the text."""
        result = _run(generalise=False)
        token = result.audit_records[0]["pseudonym_token"]
        assert token.startswith("[IN_PHONE_")
        assert token in result.anonymised_text
        assert "+91 XXXXX" not in result.anonymised_text

    def test_regime_none_compliance_is_none(self) -> None:
        """AC1 — compliance is opt-in."""
        assert _run().compliance is None

    def test_regime_given_returns_compliance_report(self) -> None:
        """AC1 — a regime yields a ComplianceReport wired with generated_at."""
        result = _run(regime=DPDPRegime())
        assert isinstance(result.compliance, ComplianceReport)
        assert result.compliance.generated_at == _TS
        assert result.audit_row["payload"]["regime_id"] == "DPDP-2023"

    def test_empty_text_returns_zero_entity_result_with_audit_row(self) -> None:
        """AC1 — empty input still appends a zero-entity attestation row."""
        result = _run(text="   ", detections=[])
        assert result.anonymised_text == "   "
        assert result.detections == ()
        assert result.audit_row["payload"]["entities_detected"] == 0
        assert verify_chain([result.audit_row])["valid"] is True

    def test_empty_key_raises_hmac_key_required(self) -> None:
        """AC1 failure path — empty key fails fast, no partial result."""
        with pytest.raises(HMACKeyRequiredError):
            anonymise(
                _TEXT,
                detector=FakeDetector([]),
                key="",
                generated_at=_TS,
            )

    def test_audit_row_chains_from_prev_hash_and_verifies(self) -> None:
        """AC1 — two successive calls form a verifiable chain."""
        first = _run()
        second = _run(prev_hash=first.audit_row["hash"])
        assert first.audit_row["prev_hash"] == GENESIS_PREV_HASH
        assert second.audit_row["prev_hash"] == first.audit_row["hash"]
        assert verify_chain([first.audit_row, second.audit_row])["valid"] is True

    def test_audit_payload_contains_no_pii(self) -> None:
        """AC1/security — payload carries counts and hashes only."""
        result = _run()
        serialised = json.dumps(result.audit_row["payload"])
        for det in result.detections:
            assert det["text"] not in serialised
        for record in result.audit_records:
            assert record["pseudonym_token"] not in serialised
        assert result.audit_row["payload"]["entity_summary"] == {
            "IN_PHONE": 1,
            "IN_PAN": 1,
        }

    def test_anonymise_is_deterministic(self) -> None:
        """AC1 — identical inputs give byte-identical row hashes (no clock)."""
        assert _run().audit_row["hash"] == _run().audit_row["hash"]

    def test_zip_alignment_with_unordered_detector_output(self) -> None:
        """Risk R1 — out-of-start-order detector output still pairs each
        pseudonym token with the right detection in the generalisation step."""
        result = _run(detections=[_PAN, _PHONE])  # deliberately reversed
        # Phone generalisation keeps ITS last 3 digits — a mispaired zip
        # would have routed the PAN value through generalise_phone instead.
        assert "+91 XXXXX XX210" in result.anonymised_text
        assert result.detections[0]["entity_type"] == "IN_PHONE"
        assert result.audit_records[0]["pseudonym_token"].startswith("[IN_PHONE_")
