# SPDX-License-Identifier: MIT
"""Presidio engine test fixture — a ready-to-use Indian-PII ``AnalyzerEngine``.

``presidio_engine_indian`` returns the engine built by BILTIQ-002's
``build_engine()`` with all eight Indian recognisers registered. It is
**session-scoped** so the ~2–4 s spaCy ``en_core_web_sm`` cold-load is paid
once for the whole suite rather than per test (mirrors the module-scoped
``engine`` fixture already inside ``tests/indian/test_recognisers.py``, but
shared suite-wide via conftest re-export).

``docs/architecture/stack.md`` § Test fixtures reserved this fixture name;
until BILTIQ-009 it did not exist (only ``hmac_key`` and the local engine
fixture did). The detector tests (BILTIQ-009 Step 4) and the BILTIQ-012
orchestrator tests consume it.

The fixture *body* — not module import — calls ``build_engine()``, so merely
collecting this module does not cold-load spaCy; the cost is deferred until a
test first requests the fixture.
"""
from __future__ import annotations

import pytest
from presidio_analyzer import AnalyzerEngine

from biltiq_privacy.indian.recognisers import build_engine


@pytest.fixture(scope="session")
def presidio_engine_indian() -> AnalyzerEngine:
    """Session-scoped ``AnalyzerEngine`` with the eight Indian recognisers.

    Built once via ``build_engine()`` and shared across the suite to amortise
    the spaCy model cold-load. Tests must treat it as read-only — the engine
    carries no per-test state, so sharing across tests is safe.
    """
    return build_engine()
