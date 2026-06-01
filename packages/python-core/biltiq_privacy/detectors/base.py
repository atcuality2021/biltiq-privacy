# SPDX-License-Identifier: MIT
"""The detection abstraction: a ``Detector`` ABC + the ``DetectedEntity`` record.

CDSCO-RegAI's ``backend/modules/anonymisation/presidio_engine.py`` exposed a
single ``detect_pii_rules(text) -> list[dict]`` function. This module lifts
only the *contract* of that wrapper into a pluggable abstraction so backends
(rule-based Presidio now; LLM/hybrid from Phase D) are swappable without the
core pipeline knowing which one is wired. There is no runtime dependency on
CDSCO-RegAI, and no Presidio/spaCy/FastAPI import here — the seam stays
framework-free and import-light (spec AC1, AC5).

``DetectedEntity`` extends the shipped BILTIQ-007 ``Detection`` TypedDict with
the single ``source`` key CDSCO recorded. Because a ``TypedDict`` is a plain
``dict`` at runtime, a ``DetectedEntity`` is accepted anywhere a ``Detection``
is consumed (the pseudonymiser, the BILTIQ-012 orchestrator) without
conversion — so there is no parallel record type to keep in sync.
"""
from __future__ import annotations

import abc

from biltiq_privacy.core.pseudonymiser import Detection


class DetectedEntity(Detection):
    """A detected PII span plus the backend that found it.

    Inherits ``entity_type``, ``text``, ``start``, ``end``, ``score`` from
    :class:`~biltiq_privacy.core.pseudonymiser.Detection` and adds ``source``
    (e.g. ``"presidio"``) so downstream audit can attribute each span to its
    detector.
    """

    source: str


class Detector(abc.ABC):
    """Strategy interface every detection backend implements.

    A detector turns text into a list of :class:`DetectedEntity` records. It
    holds no key and no secret; backends own their own (lazy) model loading.
    Implementations live beside this module (e.g.
    :class:`~biltiq_privacy.detectors.presidio_backend.PresidioDetector`).
    """

    @abc.abstractmethod
    def detect(self, text: str, language: str = "en") -> list[DetectedEntity]:
        """Return the PII spans found in ``text``.

        Args:
            text: The text to scan.
            language: ISO language code passed to the backend (default
                ``"en"``).

        Returns:
            One :class:`DetectedEntity` per span the backend is confident
            about, in the backend's native result order.
        """
        raise NotImplementedError
