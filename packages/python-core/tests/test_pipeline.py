# SPDX-License-Identifier: MIT
"""Unit tests for the anonymise() facade (BILTIQ-012).

All tests run against an in-test fake detector — no Presidio/spaCy load.
The _merge_detections characterisation tests pin the CDSCO algorithm
(sort ``(start, -score)``; overlap keeps the strictly higher score).
"""
from __future__ import annotations

from biltiq_privacy.detectors.base import DetectedEntity
from biltiq_privacy.pipeline import _merge_detections


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
