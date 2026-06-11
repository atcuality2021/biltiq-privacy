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

from biltiq_privacy.detectors.base import DetectedEntity


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
