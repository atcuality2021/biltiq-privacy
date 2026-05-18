# SPDX-License-Identifier: MIT
"""Indian PII Presidio adapter — eight PatternRecognizers + engine factory.

This module exposes:

* Eight module-level ``PatternRecognizer`` instances — one per spec.html
  AC2 entity, each referencing its regex string from
  :mod:`biltiq_privacy.indian.patterns` by name (AC3 single-source-of-truth).
* ``INDIAN_RECOGNISERS`` — immutable ``Sequence[PatternRecognizer]`` of
  all eight, in spec canonical order.
* ``build_engine()`` — pure factory returning a fresh ``AnalyzerEngine``
  with all eight registered. No module-global singleton; consumers own
  the engine lifecycle (spec.html § Out of Scope §1).

AC11 source attribution
-----------------------

Recogniser shape — entity-type names, ``Pattern`` layout, baseline
confidence scores — is sourced from the CDSCO-RegAI internal regulatory
codebase, specifically:

* ``CDSCO-RegAI:backend/modules/anonymisation/presidio_engine.py`` — eight
  ``PatternRecognizer`` instances with confidence scores tuned against
  CDSCO production traffic. The MED_REG score of 0.6 is locked by
  spec.html § Out of Scope §7.

Productisation differences from CDSCO-RegAI
-------------------------------------------

* No module-global ``_engine`` singleton. CDSCO caches the engine via
  a ``get_engine()`` lazy-init pattern; ``biltiq_privacy`` ships
  ``build_engine()`` as a pure factory and lets consumers own the
  singleton lifecycle.
* Regex strings reference the constants in
  :mod:`biltiq_privacy.indian.patterns` rather than being inlined into
  the ``Pattern`` constructor (AC3 — verified by ``test_invariants.py``).
* Per-entity context-word lists are attached for Presidio's
  context-boost scoring. CDSCO ships without context words; the
  ``biltiq_privacy`` SDK is consumed in more diverse text surfaces
  (logs, free-form prose, ATC chat transcripts) where context-boost
  meaningfully reduces false-negatives at the cost of negligible
  false-positive risk.

Compliance posture
------------------

Per spec.html § Compliance: this module performs no I/O at import time
and no network calls at any time. ``build_engine(nlp_engine=None)`` lets
Presidio construct its default in-process spaCy engine; passing a
pre-built ``NlpEngine`` lets consumers wire alternative on-prem NLP
backends without modifying this module.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngine, NlpEngineProvider

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

# ---------------------------------------------------------------------------
# Eight PatternRecognizer instances — confidence scores match
# CDSCO-RegAI:presidio_engine.py production values. AC3 invariant: every
# ``Pattern.regex`` argument references a ``Final[str]`` constant imported
# from ``patterns.py`` — no string literal duplication.
#
# Entity type names (``IN_*``) follow Presidio's convention of namespacing
# country-specific entities and match spec.html AC2.
# ---------------------------------------------------------------------------

_AADHAAR: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_AADHAAR",
    name="Indian Aadhaar Recogniser",
    patterns=[Pattern(name="aadhaar", regex=AADHAAR_PATTERN, score=0.95)],
    context=["aadhaar", "aadhar", "uid", "uidai"],
    supported_language="en",
)

_PAN: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_PAN",
    name="Indian PAN Recogniser",
    patterns=[Pattern(name="pan", regex=PAN_PATTERN, score=0.9)],
    context=["pan", "permanent account number", "income tax"],
    supported_language="en",
)

_ABHA: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_ABHA",
    name="Indian ABHA Recogniser",
    patterns=[Pattern(name="abha", regex=ABHA_PATTERN, score=0.85)],
    context=["abha", "ayushman", "health account", "abdm"],
    supported_language="en",
)

_GSTIN: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_GSTIN",
    name="Indian GSTIN Recogniser",
    patterns=[Pattern(name="gstin", regex=GSTIN_PATTERN, score=0.9)],
    context=["gstin", "gst", "goods and services"],
    supported_language="en",
)

_VOTER_ID: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_VOTER_ID",
    name="Indian Voter ID Recogniser",
    patterns=[Pattern(name="voter_id", regex=VOTER_ID_PATTERN, score=0.7)],
    context=["voter id", "epic", "elector"],
    supported_language="en",
)

_IFSC: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_IFSC",
    name="Indian IFSC Recogniser",
    patterns=[Pattern(name="ifsc", regex=IFSC_PATTERN, score=0.85)],
    context=["ifsc", "bank", "branch code"],
    supported_language="en",
)

_PHONE: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_PHONE",
    name="Indian Phone Recogniser",
    patterns=[Pattern(name="phone_in", regex=PHONE_IN_PATTERN, score=0.9)],
    context=["phone", "mobile", "contact"],
    supported_language="en",
)

_MED_REG: Final[PatternRecognizer] = PatternRecognizer(
    supported_entity="IN_MEDICAL_REG",
    name="Indian Medical Registration Recogniser",
    patterns=[Pattern(name="med_reg", regex=MEDICAL_REG_PATTERN, score=0.6)],
    context=["registration", "medical council", "registration number"],
    supported_language="en",
)


# ---------------------------------------------------------------------------
# Immutable tuple — iteration order is spec canonical (AADHAAR..MED_REG).
# Adapters that want a different order or subset should construct their own
# Sequence; this constant ships the eight-recogniser default.
# ---------------------------------------------------------------------------

INDIAN_RECOGNISERS: Final[Sequence[PatternRecognizer]] = (
    _AADHAAR,
    _PAN,
    _ABHA,
    _GSTIN,
    _VOTER_ID,
    _IFSC,
    _PHONE,
    _MED_REG,
)


def build_engine(nlp_engine: NlpEngine | None = None) -> AnalyzerEngine:
    """Build a fresh ``AnalyzerEngine`` with all eight Indian recognisers.

    Pure factory — every call returns a new engine. There is no
    module-global singleton (spec.html § Out of Scope §1); consumers
    should construct the engine once and cache the return value
    themselves.

    Args
    ----
    nlp_engine:
        Optional pre-constructed Presidio NLP engine. When ``None``,
        a fresh ``NlpEngineProvider`` is constructed and configured to
        load the ``en_core_web_sm`` model (cold-start cost ~2–4 seconds;
        warm calls are ~50 ms). We pin ``en_core_web_sm`` explicitly
        rather than letting Presidio default to ``en_core_web_lg``
        because the BiltIQ privacy SDK bundles ``sm`` only (ADR-0002).
        Pass a pre-built ``NlpEngine`` when multiple ``build_engine()``
        calls share a single NLP backend or when wiring an alternative
        on-prem model.

    Returns
    -------
    AnalyzerEngine
        Fresh engine with the eight Indian recognisers registered and
        ``supported_languages=["en"]``. Does not include any other
        Presidio default recognisers — register additional language /
        region packs against the returned engine's ``registry`` if
        needed.
    """
    if nlp_engine is None:
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
        ).create_engine()
    engine = AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["en"],
    )
    for recogniser in INDIAN_RECOGNISERS:
        engine.registry.add_recognizer(recogniser)
    return engine
