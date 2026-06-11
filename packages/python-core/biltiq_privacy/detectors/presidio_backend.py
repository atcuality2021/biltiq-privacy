# SPDX-License-Identifier: MIT
"""``PresidioDetector`` — the rule-based detection backend.

Ports the behaviour of CDSCO-RegAI's
``backend/modules/anonymisation/presidio_engine.py`` ``detect_pii_rules()``
wrapper into a :class:`~biltiq_privacy.detectors.base.Detector`. It reuses
BILTIQ-002's :func:`biltiq_privacy.indian.recognisers.build_engine` verbatim —
no recogniser is re-defined here (spec AC2) — and projects each Presidio
``RecognizerResult`` into a :class:`~biltiq_privacy.detectors.base.DetectedEntity`.

Productisation differences from CDSCO-RegAI
-------------------------------------------

* **Instance-level lazy singleton.** CDSCO caches the engine in a module
  global; this backend builds the engine on the first :meth:`detect` call and
  stores it on ``self._engine`` (spec AC3), so each detector owns its own
  engine lifecycle and there is no shared module state.
* **Configurable threshold.** The CDSCO wrapper hard-codes a 0.5 confidence
  floor; here it is the ``score_threshold`` constructor argument, defaulting
  to ``0.5`` to preserve CDSCO behaviour (spec AC4).
* **Typed missing-model failure.** A missing ``en_core_web_sm`` surfaces as
  :class:`~biltiq_privacy.core.exceptions.MissingNERModelError` carrying the
  install hint, rather than a raw spaCy ``OSError`` (spec AC3).

Lazy-import contract (spec AC5)
-------------------------------

Importing this module loads neither ``presidio_analyzer`` nor ``spacy``. The
only Presidio reference at module scope is the :class:`AnalyzerEngine`
annotation, kept import-free via ``from __future__ import annotations`` plus a
:data:`typing.TYPE_CHECKING` guard. ``build_engine`` is imported inside
:meth:`detect`, so the heavy stack is pulled in only when detection actually
runs. ``tests/detectors/test_lazy_import.py`` pins this with a subprocess probe.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from biltiq_privacy.core.exceptions import MissingNERModelError
from biltiq_privacy.detectors.base import DetectedEntity, Detector

if TYPE_CHECKING:  # pragma: no cover - import-time-only typing aid
    from presidio_analyzer import AnalyzerEngine


class PresidioDetector(Detector):
    """Rule-based PII detector backed by Presidio + the Indian recogniser pack.

    Args:
        score_threshold: Minimum confidence a span must carry to be returned.
            Defaults to ``0.5``, matching the CDSCO-RegAI wrapper. Spans scoring
            below this (after Presidio's own context-boost scoring) are dropped.
    """

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self._score_threshold = score_threshold
        # Built on first detect() call (instance-level lazy singleton, AC3).
        self._engine: AnalyzerEngine | None = None

    def detect(self, text: str, language: str = "en") -> list[DetectedEntity]:
        """Return the PII spans Presidio finds in ``text``.

        Builds the analyzer engine on first call and reuses it thereafter.
        Each returned record is a six-key :class:`DetectedEntity`
        (``entity_type``, ``text``, ``start``, ``end``, ``score``, ``source``)
        with ``source == "presidio"`` and ``score`` rounded to 4 decimal
        places, mirroring the CDSCO projection.

        Raises:
            MissingNERModelError: If the spaCy ``en_core_web_sm`` model cannot
                be loaded (the original ``OSError`` is chained via ``__cause__``).
        """
        engine = self._engine
        if engine is None:
            # Method-level import keeps Presidio/spaCy out of module import (AC5).
            from biltiq_privacy.indian.recognisers import build_engine

            try:
                engine = build_engine()
            except OSError as err:
                # spaCy raises OSError when the NER model is absent; surface a
                # typed, actionable error and chain the cause (AP #3 — scoped
                # catch, never bare; non-OSError faults propagate untouched).
                raise MissingNERModelError(
                    "Presidio could not load the spaCy NER model."
                ) from err
            self._engine = engine

        results = engine.analyze(text=text, language=language)
        return [
            DetectedEntity(
                entity_type=result.entity_type,
                text=text[result.start : result.end],
                start=result.start,
                end=result.end,
                score=round(result.score, 4),
                source="presidio",
            )
            for result in results
            if result.score >= self._score_threshold
        ]
