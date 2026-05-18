# SPDX-License-Identifier: MIT
"""Indian PII recogniser tests — adapter shape + happy-path detection.

Covers AC2 (eight entity types via PatternRecognizer) and AC6 (each
recogniser detects at least one known-valid fixture). AC3 (no string
duplication across patterns.py and recognisers.py) is tested separately
in test_invariants.py — that test belongs to step 6 of the build plan.

The module-scoped ``engine`` fixture amortises Presidio's spaCy model
cold-load (~2–4 s) across the eight detection tests. The
``test_build_engine_returns_fresh_instance`` test does NOT reuse the
fixture — it asserts the pure-factory invariant by calling
``build_engine()`` twice.
"""
from __future__ import annotations

import pytest
from presidio_analyzer import AnalyzerEngine, PatternRecognizer

from biltiq_privacy.indian.recognisers import (
    INDIAN_RECOGNISERS,
    build_engine,
)

# Expected entity-type names per spec.html line 152-154.
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

# One known-valid fixture per entity (drawn from tests.fixtures.india
# tuples, verified during Step 4 against the regex). Kept inline here
# rather than re-imported to keep the recogniser test surface
# independent of the fixture file's tuple naming.
DETECTION_CASES: tuple[tuple[str, str], ...] = (
    ("IN_AADHAAR", "1234 5678 9011"),
    ("IN_PAN", "ABCDE1234F"),
    ("IN_ABHA", "12-3456-7890-1234"),
    ("IN_GSTIN", "27ABCDE1234F1Z5"),
    ("IN_VOTER_ID", "ABC1234567"),
    ("IN_IFSC", "HDFC0001234"),
    ("IN_PHONE", "9876543210"),
    ("IN_MEDICAL_REG", "MCI12345"),
)


@pytest.fixture(scope="module")
def engine() -> AnalyzerEngine:
    """Module-scoped engine — amortises spaCy cold-load across detection tests."""
    return build_engine()


def test_recognisers_tuple_shape() -> None:
    """INDIAN_RECOGNISERS contains exactly 8 PatternRecognizer instances."""
    assert len(INDIAN_RECOGNISERS) == 8, (
        f"expected 8 recognisers, got {len(INDIAN_RECOGNISERS)}"
    )
    for rec in INDIAN_RECOGNISERS:
        assert isinstance(rec, PatternRecognizer), (
            f"non-PatternRecognizer in tuple: {type(rec).__name__}"
        )


def test_recognisers_entity_types_match_spec() -> None:
    """Each recogniser declares one of the eight expected IN_* entity types.

    Note: Presidio's ``PatternRecognizer`` constructor takes
    ``supported_entity`` (singular) but the ``EntityRecognizer`` base
    class stores it as the ``supported_entities`` list attribute.
    """
    actual = {ent for rec in INDIAN_RECOGNISERS for ent in rec.supported_entities}
    assert actual == set(EXPECTED_ENTITY_TYPES), (
        f"entity-type mismatch — expected {sorted(EXPECTED_ENTITY_TYPES)}, "
        f"got {sorted(actual)}"
    )


def test_recognisers_one_pattern_each() -> None:
    """Each recogniser registers exactly one Pattern (AC2 surface — no
    multi-pattern recognisers in the Indian pack)."""
    for rec in INDIAN_RECOGNISERS:
        assert len(rec.patterns) == 1, (
            f"{rec.supported_entities[0]} has {len(rec.patterns)} patterns "
            f"(expected exactly 1)"
        )


def test_build_engine_returns_fresh_instance() -> None:
    """``build_engine()`` returns a new AnalyzerEngine on each call.

    Validates the pure-factory contract from spec.html § Out of Scope §1
    (no module-global singleton).
    """
    first = build_engine()
    second = build_engine()
    assert first is not second, "build_engine() returned cached singleton"
    assert isinstance(first, AnalyzerEngine)
    assert isinstance(second, AnalyzerEngine)


def test_build_engine_registers_all_indian_recognisers(
    engine: AnalyzerEngine,
) -> None:
    """The engine returned by build_engine() lists all eight IN_* entities."""
    supported = set(engine.get_supported_entities(language="en"))
    missing = EXPECTED_ENTITY_TYPES - supported
    assert not missing, (
        f"build_engine() failed to register entities: {sorted(missing)}"
    )


@pytest.mark.parametrize(("expected_entity", "text"), DETECTION_CASES)
def test_engine_detects_each_entity(
    engine: AnalyzerEngine,
    expected_entity: str,
    text: str,
) -> None:
    """The engine detects each expected entity in its known-valid fixture (AC6).

    Filters the analyze() call to ``entities=[expected_entity]`` so the
    test asserts the specific recogniser fired (rather than just any
    detection occurring).
    """
    results = engine.analyze(
        text=text,
        language="en",
        entities=[expected_entity],
    )
    assert any(r.entity_type == expected_entity for r in results), (
        f"engine failed to detect {expected_entity} in {text!r}; "
        f"results={[(r.entity_type, r.score) for r in results]!r}"
    )
