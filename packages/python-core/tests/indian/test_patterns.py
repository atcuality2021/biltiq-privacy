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

from biltiq_privacy.indian.patterns import PATTERNS, redact
from tests.fixtures import india as fixtures

logger = logging.getLogger(__name__)

# Entity names mirror the keys of PATTERNS and the {ENTITY}_VALID /
# {ENTITY}_FALSE_POSITIVES naming convention in tests.fixtures.india.
# Per spec.html AC2 + design.html § Eight Entity Types.
ENTITIES: tuple[str, ...] = (
    "AADHAAR",
    "PAN",
    "ABHA",
    "GSTIN",
    "VOTER_ID",
    "IFSC",
    "PHONE_IN",
    "MEDICAL_REG",
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


def test_redact_preserves_structure() -> None:
    """redact() replaces PII spans with [REDACTED-<ENTITY>] tags but preserves
    surrounding text (AC4 — redaction surface contract)."""
    text = "Aadhaar 1234 5678 9011 and PAN ABCDE1234F end."
    result = redact(text)
    # PII spans removed
    assert "1234 5678 9011" not in result, "Aadhaar span leaked into output"
    assert "ABCDE1234F" not in result, "PAN span leaked into output"
    # Replacement tags present
    assert "[REDACTED-AADHAAR]" in result, "AADHAAR tag not emitted"
    assert "[REDACTED-PAN]" in result, "PAN tag not emitted"
    # Surrounding text preserved verbatim
    assert result.startswith("Aadhaar "), "leading non-PII text mangled"
    assert " and PAN " in result, "interstitial text mangled"
    assert result.endswith(" end."), "trailing non-PII text mangled"


def test_redact_order_abha_before_aadhaar() -> None:
    """ABHA must be detected as ABHA, not as embedded AADHAAR (AC4 + _REDACT_ORDER).

    The ABHA format NN-NNNN-NNNN-NNNN contains a substring matching the
    AADHAAR pattern NNNN-NNNN-NNNN after the leading NN-. Without
    ABHA-first ordering, redact() would tag only the embedded 12-digit
    span and leak the leading 2-digit ABHA prefix.
    """
    text = "12-3456-7890-1234"  # synthetic ABHA fixture shape
    result = redact(text)
    assert "[REDACTED-ABHA]" in result, (
        f"ABHA-shaped input redacted incorrectly — got {result!r}"
    )
    assert "[REDACTED-AADHAAR]" not in result, (
        f"AADHAAR matched embedded substring of ABHA — got {result!r}"
    )
    # And the digits themselves should be gone.
    assert "3456" not in result and "7890" not in result, (
        f"ABHA digit groups leaked — got {result!r}"
    )
