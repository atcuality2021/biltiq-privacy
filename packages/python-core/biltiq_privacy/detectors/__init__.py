# SPDX-License-Identifier: MIT
"""Pluggable detection backends.

Re-exports the detection seam (:class:`Detector`, :class:`DetectedEntity`) and
the default rule-based backend (:class:`PresidioDetector`). Importing this
package stays lazy: ``PresidioDetector`` defers every Presidio/spaCy import to
``detect()`` (spec AC5), so ``from biltiq_privacy.detectors import …`` triggers
no model load. Additional backends (LLM / hybrid) land beside these from
Phase D and implement the same :class:`Detector` ABC.
"""
from __future__ import annotations

from biltiq_privacy.detectors.base import DetectedEntity, Detector
from biltiq_privacy.detectors.presidio_backend import PresidioDetector

__all__ = [
    "DetectedEntity",
    "Detector",
    "PresidioDetector",
]
