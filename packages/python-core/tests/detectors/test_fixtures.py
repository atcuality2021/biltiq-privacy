# SPDX-License-Identifier: MIT
"""Fixture self-checks for the BILTIQ-009 detector tests (Step 3).

These guard the Step-4 detector test against a *vacuous* pass. If the shared
``sample_indian_pii`` blob silently lost an entity, or the
``presidio_engine_indian`` fixture failed to register a recogniser, the
detection test could "pass" while detecting fewer than the eight entities it
claims to cover. Pinning both invariants here makes that failure mode loud
and local rather than a silent gap downstream (AC6 support).
"""
from __future__ import annotations

from presidio_analyzer import AnalyzerEngine

from biltiq_privacy.indian.patterns import PATTERNS

# The eight IN_* entity types the engine must register — mirrors
# tests/indian/test_recognisers.py::EXPECTED_ENTITY_TYPES.
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


def test_sample_indian_pii_covers_all_entities(sample_indian_pii: str) -> None:
    """Every one of the eight entity regexes matches in the sample blob.

    Ties the fixture to the *actual* detection patterns (``patterns.PATTERNS``,
    the regexes the Indian recognisers wrap), so the Step-4 detection test
    cannot pass over a blob that is missing an entity. Success path.
    """
    missing = [
        key for key, pattern in PATTERNS.items()
        if pattern.search(sample_indian_pii) is None
    ]
    assert not missing, (
        f"sample_indian_pii has no value matching: {sorted(missing)} — "
        f"a Step-4 detection assertion over this blob would be vacuous"
    )


def test_presidio_engine_indian_registers_eight(
    presidio_engine_indian: AnalyzerEngine,
) -> None:
    """The shared engine fixture registers all eight IN_* entities.

    Sanity guard that the fixture wires BILTIQ-002's ``build_engine()``
    correctly — if a recogniser dropped out, detection would silently miss it.
    """
    supported = set(presidio_engine_indian.get_supported_entities(language="en"))
    missing = EXPECTED_ENTITY_TYPES - supported
    assert not missing, (
        f"presidio_engine_indian failed to register: {sorted(missing)}"
    )
