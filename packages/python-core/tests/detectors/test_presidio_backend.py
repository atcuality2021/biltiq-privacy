# SPDX-License-Identifier: MIT
"""Behavioural + failure-path tests for ``PresidioDetector`` (BILTIQ-009 Step 4).

Pins the CDSCO ``detect_pii_rules()`` port:

* AC2/AC6 — detects each of the eight Indian entity types via the reused
  ``build_engine()`` (no recogniser re-defined here).
* AC3 — instance-level lazy singleton (engine built once, reused); a missing
  spaCy model maps to ``MissingNERModelError`` with install guidance, and a
  non-``OSError`` build fault propagates unwrapped.
* AC4 — the ``score_threshold`` constructor arg filters low-confidence spans;
  default ``0.5`` preserves CDSCO behaviour.
* Projection fidelity — six-key records, ``source == "presidio"``,
  ``round(score, 4)``.

Threshold assertions deliberately run over a *context-free* string so each
span carries its recogniser's nominal score. The labelled ``sample_indian_pii``
blob triggers Presidio's context-aware enhancer (e.g. "Voter" boosts
``IN_VOTER_ID`` from 0.70 to 1.0), which would mask threshold filtering.
"""
from __future__ import annotations

import importlib

import pytest

from biltiq_privacy.core.exceptions import MissingNERModelError
from biltiq_privacy.detectors.base import DetectedEntity
from biltiq_privacy.detectors.presidio_backend import PresidioDetector

# The eight IN_* entity types the Indian pack registers.
EXPECTED_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "IN_AADHAAR",
        "IN_PAN",
        "IN_ABHA",
        "IN_GSTIN",
        "IN_VOTER_ID",
        "IN_IFSC",
        "IN_PHONE",
        "IN_MEDICAL_REG",
    }
)

# Context-free values (no surrounding label words) so Presidio's context-aware
# enhancer does not boost scores above each recogniser's nominal floor:
# IN_PAN/IN_GSTIN/IN_PHONE @0.9, IN_VOTER_ID @0.7, IN_MEDICAL_REG @0.6. All
# values are synthetic, drawn from tests/fixtures/india.py *_VALID tuples.
_CONTEXT_FREE_PII: str = "ABCDE1234F 27ABCDE1234F1Z5 9876543210 ABC1234567 MCI12345"

_SIX_KEYS: frozenset[str] = frozenset(
    {"entity_type", "text", "start", "end", "score", "source"}
)


def _in_entity_types(detections: list[DetectedEntity]) -> set[str]:
    """The IN_* entity types present in ``detections`` (ignoring Presidio
    built-ins like PERSON / DATE_TIME that ``build_engine()`` also registers)."""
    return {d["entity_type"] for d in detections if d["entity_type"].startswith("IN_")}


@pytest.fixture(scope="module")
def detector() -> PresidioDetector:
    """Default-threshold detector, module-scoped to amortise the engine build."""
    return PresidioDetector()


def test_detects_each_indian_entity(
    detector: PresidioDetector, sample_indian_pii: str
) -> None:
    """All eight IN_* entity types surface in the sample blob (AC2/AC6)."""
    detections = detector.detect(sample_indian_pii)
    found = _in_entity_types(detections)
    missing = EXPECTED_ENTITY_TYPES - found
    assert not missing, f"undetected Indian entity types: {sorted(missing)}"


def test_records_have_six_keys_and_presidio_source(
    detector: PresidioDetector, sample_indian_pii: str
) -> None:
    """Every record is the six-key DetectedEntity shape with source=presidio."""
    detections = detector.detect(sample_indian_pii)
    assert detections, "expected at least one detection on the sample blob"
    for record in detections:
        assert set(record) == _SIX_KEYS, f"unexpected key set: {sorted(record)}"
        assert record["source"] == "presidio"
        assert record["text"] == sample_indian_pii[record["start"] : record["end"]]


def test_score_is_rounded_4dp(
    detector: PresidioDetector, sample_indian_pii: str
) -> None:
    """Every returned score equals round(score, 4) (CDSCO projection fidelity)."""
    for record in detector.detect(sample_indian_pii):
        assert record["score"] == round(record["score"], 4)


def test_default_threshold_keeps_low_confidence(detector: PresidioDetector) -> None:
    """At the default 0.5 floor, the 0.6/0.7 entities are retained (AC4)."""
    found = _in_entity_types(detector.detect(_CONTEXT_FREE_PII))
    assert {"IN_VOTER_ID", "IN_MEDICAL_REG"} <= found, (
        f"default 0.5 threshold dropped low-confidence entities: found {sorted(found)}"
    )


def test_raised_threshold_drops_low_confidence() -> None:
    """A 0.8 threshold drops Voter ID (0.7) + Medical Reg (0.6), keeps 0.9s (AC4)."""
    found = _in_entity_types(PresidioDetector(score_threshold=0.8).detect(_CONTEXT_FREE_PII))
    assert "IN_VOTER_ID" not in found, "0.8 threshold should drop IN_VOTER_ID @0.7"
    assert "IN_MEDICAL_REG" not in found, "0.8 threshold should drop IN_MEDICAL_REG @0.6"
    assert {"IN_PAN", "IN_GSTIN", "IN_PHONE"} <= found, (
        f"0.8 threshold should keep the 0.9 entities: found {sorted(found)}"
    )


def test_engine_is_lazy_singleton() -> None:
    """Engine is None until first detect(), then reused across calls (AC3)."""
    detector = PresidioDetector()
    assert detector._engine is None, "engine must not be built at construction"
    detector.detect("ABCDE1234F")
    first = detector._engine
    assert first is not None, "engine must be built on first detect()"
    detector.detect("9876543210")
    assert detector._engine is first, "second detect() must reuse the same engine"


def test_missing_ner_model_maps_to_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError at engine build -> MissingNERModelError + guidance + cause (AC3)."""
    import biltiq_privacy.indian.recognisers as recognisers

    def _raise_oserror() -> object:
        raise OSError("Can't find model 'en_core_web_sm'")

    monkeypatch.setattr(recognisers, "build_engine", _raise_oserror)
    with pytest.raises(MissingNERModelError) as exc_info:
        PresidioDetector().detect("ABCDE1234F")
    assert "spacy download en_core_web_sm" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, OSError)


def test_non_oserror_build_fault_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-OSError build fault is NOT swallowed — proves the catch is scoped."""
    import biltiq_privacy.indian.recognisers as recognisers

    def _raise_valueerror() -> object:
        raise ValueError("unrelated configuration error")

    monkeypatch.setattr(recognisers, "build_engine", _raise_valueerror)
    with pytest.raises(ValueError, match="unrelated configuration error"):
        PresidioDetector().detect("ABCDE1234F")


def test_empty_text_returns_empty_list(detector: PresidioDetector) -> None:
    """detect('') returns [] — empty-input guard path."""
    assert detector.detect("") == []


# --- BILTIQ-012 AC7: model-distribution behaviour (ADR-0006) -----------------
# The published dist ships without en_core_web_sm (PyPI rejects direct-URL
# deps), so the missing-model state is a real first-run path. The dev env HAS
# the model installed, so the absent precondition is simulated by patching
# build_engine; the download helper is patched alongside it (no network in
# tests — the only mocks in this module).


def test_missing_model_default_raises_with_both_remedies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7 — default (no opt-in): typed error naming flag AND post-install."""
    import biltiq_privacy.indian.recognisers as recognisers

    def _raise_oserror() -> object:
        raise OSError("Can't find model 'en_core_web_sm'")

    monkeypatch.setattr(recognisers, "build_engine", _raise_oserror)
    with pytest.raises(MissingNERModelError) as exc_info:
        PresidioDetector().detect("ABCDE1234F")
    message = str(exc_info.value)
    assert "auto_download_model=True" in message
    assert "spacy download en_core_web_sm" in message


def test_auto_download_true_invokes_spacy_download_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7 — opt-in: download helper called exactly once, then engine builds."""
    # spacy.cli re-exports the download *function* under the same name as its
    # defining submodule, so attribute traversal lands on the function;
    # import_module reaches the module itself for patching.
    download_module = importlib.import_module("spacy.cli.download")

    import biltiq_privacy.indian.recognisers as recognisers

    calls: list[str] = []

    class _FakeEngine:
        def analyze(self, text: str, language: str) -> list[object]:
            return []

    sentinel_engine = _FakeEngine()

    def _fake_build_engine() -> object:
        if not calls:  # model "absent" until the download has happened
            raise OSError("Can't find model 'en_core_web_sm'")
        return sentinel_engine

    def _fake_download(model: str) -> None:
        calls.append(model)

    monkeypatch.setattr(recognisers, "build_engine", _fake_build_engine)
    monkeypatch.setattr(download_module, "download", _fake_download)

    detector = PresidioDetector(auto_download_model=True)
    detector.detect("")  # empty text short-circuits analyze; engine still builds
    assert calls == ["en_core_web_sm"]
    # _engine is annotated AnalyzerEngine | None; the fake makes the identity
    # check non-overlapping for mypy, so compare via object identity helper.
    assert id(detector._engine) == id(sentinel_engine)


def test_default_path_makes_no_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7 — model present + defaults: the download helper is never touched
    (on_prem_preferred guard)."""
    download_module = importlib.import_module("spacy.cli.download")

    def _explode(model: str) -> None:
        raise AssertionError(f"network download attempted for {model!r}")

    monkeypatch.setattr(download_module, "download", _explode)
    detections = PresidioDetector().detect("ABCDE1234F")
    assert any(d["entity_type"] == "IN_PAN" for d in detections)
