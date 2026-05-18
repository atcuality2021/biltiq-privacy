# SPDX-License-Identifier: MIT
"""Indian PII regex pack — pure-stdlib detectors for eight ID formats.

This module exposes:

* Eight ``Final[str]`` regex constants — one per spec.html AC2 entity.
* A compiled ``PATTERNS`` mapping — single import surface for adapters.
* ``_REDACT_ORDER`` — fixed iteration order for ``redact()``.
* ``redact()`` — pure-``re`` redactor that replaces recognised spans with
  ``[REDACTED-<ENTITY>]`` tags.

AC11 source attribution
-----------------------

Regex strings are sourced from the CDSCO-RegAI internal regulatory codebase
and re-implemented here as a productisation step for the OSS
``biltiq-privacy`` SDK. There is no runtime dependency on CDSCO-RegAI; only
the regex string content is duplicated. The originating files are:

* ``CDSCO-RegAI:backend/utils/pii_patterns.py`` — Aadhaar, PAN, and ABHA
  regex strings and the original ``redact()`` reference implementation.
* ``CDSCO-RegAI:backend/modules/anonymisation/presidio_engine.py`` — full
  eight-entity recognizer set including GSTIN, VOTER_ID, IFSC, PHONE_IN,
  and MEDICAL_REG patterns and their confidence scores.

AC3 single-source-of-truth
--------------------------

Each regex string is declared exactly once as a module-level ``Final[str]``
constant. Adapters (e.g. ``biltiq_privacy.indian.recognisers``) reference
the constants by name — they do not re-declare the string literal. The
``PATTERNS`` dict's compiled regexes preserve the original string via
``re.Pattern[str].pattern`` (which returns the exact object passed to
``re.compile``); the AC3 invariant test asserts this identity holds.

AC5 lazy-import contract
------------------------

This module imports only the standard-library ``re`` and ``typing`` modules.
Heavy optional dependencies (``presidio_analyzer``, ``spacy``) are imported
in ``biltiq_privacy.indian.recognisers`` only when the recogniser factory
is invoked. The AC5 subprocess test asserts that importing this module
does not load ``presidio_analyzer`` or ``spacy`` into ``sys.modules``.
"""
from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Regex constants — eight Indian PII entity patterns.
# Order mirrors spec.html AC2 entity list. Confidence scores (kept in
# recognisers.py adapter) match CDSCO-RegAI:presidio_engine.py.
# ---------------------------------------------------------------------------

AADHAAR_PATTERN: Final[str] = r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
PAN_PATTERN: Final[str] = r"\b[A-Z]{5}\d{4}[A-Z]\b"
ABHA_PATTERN: Final[str] = r"\b\d{2}-\d{4}-\d{4}-\d{4}\b"
GSTIN_PATTERN: Final[str] = r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b"
VOTER_ID_PATTERN: Final[str] = r"\b[A-Z]{3}\d{7}\b"
IFSC_PATTERN: Final[str] = r"\b[A-Z]{4}0[A-Z0-9]{6}\b"
PHONE_IN_PATTERN: Final[str] = r"\b(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}\b"
MEDICAL_REG_PATTERN: Final[str] = (
    r"\b(?:Registration\s*(?:No|Number)[:\s]*)?[A-Z]{2,3}\d{4,6}\b"
)


# ---------------------------------------------------------------------------
# Compiled patterns dict — single import surface for adapters.
# Keys match spec.html AC2 entity names verbatim (used by Presidio adapter
# as IN_<KEY> entity types in recognisers.py).
# ---------------------------------------------------------------------------

PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "AADHAAR": re.compile(AADHAAR_PATTERN),
    "PAN": re.compile(PAN_PATTERN),
    "ABHA": re.compile(ABHA_PATTERN),
    "GSTIN": re.compile(GSTIN_PATTERN),
    "VOTER_ID": re.compile(VOTER_ID_PATTERN),
    "IFSC": re.compile(IFSC_PATTERN),
    "PHONE_IN": re.compile(PHONE_IN_PATTERN),
    "MEDICAL_REG": re.compile(MEDICAL_REG_PATTERN),
}


# ---------------------------------------------------------------------------
# Redaction order — longest / most-specific patterns first.
#
# ABHA (``NN-NNNN-NNNN-NNNN``, 14 digits + 3 dashes) contains an
# AADHAAR-shaped substring (``NNNN-NNNN-NNNN``) after its leading
# ``NN-``. Redacting AADHAAR before ABHA would tag the embedded
# 12-digit span and leak the leading 2-digit ABHA prefix. ABHA is
# therefore tried first; once consumed, the AADHAAR pattern has no
# substring to bind to.
# ---------------------------------------------------------------------------

_REDACT_ORDER: Final[tuple[str, ...]] = (
    "ABHA",
    "AADHAAR",
    "PAN",
    "GSTIN",
    "VOTER_ID",
    "IFSC",
    "PHONE_IN",
    "MEDICAL_REG",
)


def redact(text: str) -> str:
    """Replace recognised Indian PII spans with ``[REDACTED-<ENTITY>]`` tags.

    Patterns are applied in ``_REDACT_ORDER`` so that longer / more specific
    forms consume their text before shorter forms are tried (see module
    note on ABHA-before-AADHAAR).

    Returns a new string; the input is never mutated.
    """
    redacted = text
    for entity in _REDACT_ORDER:
        redacted = PATTERNS[entity].sub(f"[REDACTED-{entity}]", redacted)
    return redacted
