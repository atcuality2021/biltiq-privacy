# SPDX-License-Identifier: MIT
"""Indian PII Presidio adapter — scaffold (content lands in BILTIQ-002 step 5).

This module will hold eight ``PatternRecognizer`` instances (each consuming
its regex string by name from :mod:`biltiq_privacy.indian.patterns`), the
``RECOGNIZERS`` tuple, and the ``build_engine()`` factory. The substantive
content (including the AC11 module-level source attribution naming
``CDSCO-RegAI:backend/modules/anonymisation/presidio_engine.py``) lands in
step 5 of the build plan.
"""
from __future__ import annotations
