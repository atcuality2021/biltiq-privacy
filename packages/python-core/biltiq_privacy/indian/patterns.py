# SPDX-License-Identifier: MIT
"""Indian PII regex pack — scaffold (regex constants land in BILTIQ-002 step 4).

This module will hold the eight ``Final[str]`` regex constants, the compiled
``PATTERNS`` mapping, the ``_REDACT_ORDER`` tuple, and the pure-``re``
``redact()`` function. The substantive content (including the AC11
module-level source attribution naming
``CDSCO-RegAI:backend/utils/pii_patterns.py``) lands in step 4 of the build
plan when the dev pastes the regex strings.

At step 3 (this commit augments step 1's scaffold), ``PATTERNS`` is defined
as an empty dict so ``tests/indian/test_patterns.py`` can import it without
``ImportError``. The RED signal for step 3 is the
``test_patterns_dict_has_all_entity_keys`` assertion — it fails on the
empty dict here and flips GREEN in step 4 once the eight regex entries are
added.
"""
from __future__ import annotations

import re
from typing import Final

PATTERNS: Final[dict[str, re.Pattern[str]]] = {}
