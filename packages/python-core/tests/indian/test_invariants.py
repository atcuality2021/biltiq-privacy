# SPDX-License-Identifier: MIT
"""Cross-module invariant tests — AC3 single-source-of-truth.

The Indian PII pack ships two modules that share regex strings:

* ``biltiq_privacy.indian.patterns`` declares the eight ``Final[str]``
  regex constants (the canonical source).
* ``biltiq_privacy.indian.recognisers`` wraps each constant in a
  Presidio ``PatternRecognizer`` for the adapter layer.

AC3 (spec.html line 156) requires that each regex string is declared
**exactly once**. The recogniser layer must reference the imported
constant by name — not duplicate the literal. This test pins that
invariant: if a future refactor inlines a regex into
``Pattern(regex=...)``, the assertion fails and CI catches the drift.

Why equality, not identity
--------------------------

We assert ``recogniser.patterns[0].regex == <CONSTANT>`` rather than
``is`` because identity-on-strings is implementation-defined for
non-pool strings (and would let a regression like ``regex=AADHAAR_PATTERN[:]``
silently pass). Equality matches the spec wording exactly: the *value*
of the regex must equal the canonical declaration.
"""
from __future__ import annotations

import pytest
from presidio_analyzer import PatternRecognizer

from biltiq_privacy.indian.patterns import (
    AADHAAR_PATTERN,
    ABHA_PATTERN,
    GSTIN_PATTERN,
    IFSC_PATTERN,
    MEDICAL_REG_PATTERN,
    PAN_PATTERN,
    PHONE_IN_PATTERN,
    VOTER_ID_PATTERN,
)
from biltiq_privacy.indian.recognisers import INDIAN_RECOGNISERS

# Pin entity-type → expected regex constant. The values here are the
# imported ``Final[str]`` references; matching is by string equality.
ENTITY_TO_CANONICAL_REGEX: dict[str, str] = {
    "IN_AADHAAR": AADHAAR_PATTERN,
    "IN_PAN": PAN_PATTERN,
    "IN_ABHA": ABHA_PATTERN,
    "IN_GSTIN": GSTIN_PATTERN,
    "IN_VOTER_ID": VOTER_ID_PATTERN,
    "IN_IFSC": IFSC_PATTERN,
    "IN_PHONE": PHONE_IN_PATTERN,
    "IN_MEDICAL_REG": MEDICAL_REG_PATTERN,
}


def _recogniser_by_entity(entity_type: str) -> PatternRecognizer:
    """Locate the unique recogniser registered for ``entity_type``.

    Fails the test immediately if zero or multiple are found — this
    function defends the precondition for the per-entity invariant
    test (every IN_* type maps to exactly one recogniser).
    """
    matches = [
        rec
        for rec in INDIAN_RECOGNISERS
        if entity_type in rec.supported_entities
    ]
    assert len(matches) == 1, (
        f"expected exactly one recogniser for {entity_type}, "
        f"found {len(matches)}"
    )
    return matches[0]


@pytest.mark.parametrize(
    ("entity_type", "canonical_regex"),
    list(ENTITY_TO_CANONICAL_REGEX.items()),
)
def test_recogniser_regex_matches_canonical_constant(
    entity_type: str,
    canonical_regex: str,
) -> None:
    """AC3: each recogniser's regex must equal the patterns.py constant.

    If this fails, recognisers.py is duplicating a string literal that
    the spec requires be declared exactly once in patterns.py.
    """
    rec = _recogniser_by_entity(entity_type)
    assert len(rec.patterns) == 1, (
        f"{entity_type} has {len(rec.patterns)} patterns; AC3 invariant "
        f"check assumes exactly one"
    )
    actual_regex = rec.patterns[0].regex
    assert actual_regex == canonical_regex, (
        f"{entity_type} regex drift — recogniser declares "
        f"{actual_regex!r}, patterns.py declares {canonical_regex!r}. "
        f"The recogniser MUST reference the patterns.py constant by "
        f"name; do not inline the literal."
    )


def test_all_indian_entities_have_invariant_coverage() -> None:
    """Guard against the test map drifting from the recogniser tuple.

    If someone adds a ninth IN_* recogniser without updating
    ENTITY_TO_CANONICAL_REGEX, this test fails — keeping the AC3
    coverage and the recogniser surface in lockstep.
    """
    tuple_entities = {
        ent for rec in INDIAN_RECOGNISERS for ent in rec.supported_entities
    }
    map_entities = set(ENTITY_TO_CANONICAL_REGEX.keys())
    assert tuple_entities == map_entities, (
        f"AC3 invariant map / recogniser tuple drift — "
        f"only in tuple: {sorted(tuple_entities - map_entities)}; "
        f"only in map: {sorted(map_entities - tuple_entities)}"
    )
