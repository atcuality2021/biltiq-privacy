# SPDX-License-Identifier: MIT
"""Contract tests for ``biltiq_privacy.detectors.base`` (BILTIQ-009 Step 2).

Pins AC1: ``Detector`` is an ABC that cannot be instantiated without a
``detect`` implementation, a concrete subclass satisfies the interface, and
``DetectedEntity`` is a structural superset of the shipped BILTIQ-007
``Detection`` — so a ``list[DetectedEntity]`` flows into the pseudonymiser
(which consumes ``list[Detection]``) without conversion and there is no
parallel record type.
"""
from __future__ import annotations

import pytest

from biltiq_privacy.core.pseudonymiser import Detection, Pseudonymiser
from biltiq_privacy.detectors.base import DetectedEntity, Detector


def test_detector_is_abstract() -> None:
    """``Detector`` cannot be instantiated directly (AC1 — failure path)."""
    with pytest.raises(TypeError):
        Detector()  # type: ignore[abstract]  # proving the ABC guard at runtime


def test_concrete_subclass_satisfies_interface() -> None:
    """A minimal concrete subclass instantiates and returns 6-key records (AC1)."""

    class _StubDetector(Detector):
        def detect(self, text: str, language: str = "en") -> list[DetectedEntity]:
            return [
                DetectedEntity(
                    entity_type="IN_PAN",
                    text="ABCDE1234F",
                    start=0,
                    end=10,
                    score=0.9,
                    source="stub",
                )
            ]

    records = _StubDetector().detect("ABCDE1234F")
    assert len(records) == 1
    assert set(records[0]) == {"entity_type", "text", "start", "end", "score", "source"}
    assert records[0]["source"] == "stub"


def test_detected_entity_is_detection_superset() -> None:
    """``DetectedEntity`` adds only ``source`` and is consumed as a ``Detection``.

    The strongest form of the no-parallel-type contract: feed a
    ``DetectedEntity`` straight into ``Pseudonymiser.pseudonymise_text``, whose
    parameter is typed ``list[Detection]``, and confirm it pseudonymises the
    span — proving structural compatibility at runtime, not just by key set.
    """
    # Key-set check: superset of Detection's keys, plus exactly `source`.
    detection_keys = set(Detection.__annotations__)
    detected_keys = set(DetectedEntity.__annotations__)
    assert detection_keys <= detected_keys
    assert detected_keys - detection_keys == {"source"}

    # Runtime consumer-compat: the pseudonymiser accepts it unchanged.
    entity = DetectedEntity(
        entity_type="IN_PAN",
        text="ABCDE1234F",
        start=0,
        end=10,
        score=0.9,
        source="presidio",
    )
    pseudonymiser = Pseudonymiser(key=b"biltiq-privacy-test-hmac-key-32b")
    anonymised, audit = pseudonymiser.pseudonymise_text("ABCDE1234F", [entity])
    assert "ABCDE1234F" not in anonymised
    assert audit[0]["entity_type"] == "IN_PAN"
