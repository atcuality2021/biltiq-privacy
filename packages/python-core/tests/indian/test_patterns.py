# SPDX-License-Identifier: MIT
"""Indian PII regex tests — parameterised over fixture tuples.

This module is RED at commit (step 3) by design:

* ``PATTERNS`` is defined in step 1's scaffold as an empty dict, so
  ``test_patterns_dict_has_all_entity_keys`` fails (the 8-entity set is
  not present yet). This is the active RED signal for step 3.
* The parameterised tests collect 0 cases at step 3 (fixture tuples are
  empty per step 2); they begin yielding cases in step 4 once the dev
  pastes fixture values.

Step 4 (DEV PASTE) fills the fixture tuples AND populates ``PATTERNS``
with eight ``re.Pattern[str]`` values in the same logical commit,
flipping the suite RED→GREEN.

Three tests cover AC1 (regex matches valid PII), AC6 (regex rejects
known false-positives), and the surface contract (PATTERNS has all eight
entity keys). The matching contract: ``PATTERNS[entity_name]`` returns a
compiled ``re.Pattern[str]`` and ``pattern.search(value)`` must succeed
on every value in ``{ENTITY}_VALID`` and fail on every value in
``{ENTITY}_FALSE_POSITIVES``.
"""
from __future__ import annotations

import logging

import pytest

from biltiq_privacy.indian.patterns import PATTERNS
from tests.fixtures import india as fixtures

logger = logging.getLogger(__name__)

# Entity names mirror the keys of PATTERNS and the {ENTITY}_VALID /
# {ENTITY}_FALSE_POSITIVES naming convention in tests.fixtures.india.
ENTITIES: tuple[str, ...] = (
    "AADHAAR",
    "ABHA",
    "PAN",
    "GSTIN",
    "VOTER_ID",
    "DRIVING_LICENSE",
    "INDIAN_PASSPORT",
    "INDIAN_PHONE",
)


def _valid_cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for entity in ENTITIES:
        values: tuple[str, ...] = getattr(fixtures, f"{entity}_VALID")
        cases.extend((entity, v) for v in values)
    return cases


def _false_positive_cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for entity in ENTITIES:
        values: tuple[str, ...] = getattr(fixtures, f"{entity}_FALSE_POSITIVES")
        cases.extend((entity, v) for v in values)
    return cases


def test_patterns_dict_has_all_entity_keys() -> None:
    """PATTERNS must expose exactly the eight Indian PII entity keys (AC2 surface)."""
    assert set(PATTERNS.keys()) == set(ENTITIES), (
        f"PATTERNS surface mismatch — expected {sorted(ENTITIES)}, "
        f"got {sorted(PATTERNS.keys())}"
    )


@pytest.mark.parametrize(("entity", "value"), _valid_cases())
def test_pattern_matches_valid_fixtures(entity: str, value: str) -> None:
    """Each {ENTITY}_VALID value must be matched by PATTERNS[entity]."""
    pattern = PATTERNS[entity]
    assert pattern.search(value) is not None, (
        f"{entity} regex failed to match valid fixture: {value!r}"
    )


@pytest.mark.parametrize(("entity", "value"), _false_positive_cases())
def test_pattern_rejects_false_positives(entity: str, value: str) -> None:
    """Each {ENTITY}_FALSE_POSITIVES value must NOT be matched by PATTERNS[entity]."""
    pattern = PATTERNS[entity]
    assert pattern.search(value) is None, (
        f"{entity} regex incorrectly matched false-positive: {value!r}"
    )
