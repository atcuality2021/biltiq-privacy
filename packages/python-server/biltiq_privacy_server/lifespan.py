# SPDX-License-Identifier: MIT
"""ASGI lifespan: build the detector once, degrade observably (BILTIQ-013, AC7).

The lifespan async context manager runs on startup, before the server accepts a
request. It constructs the singleton :class:`~biltiq_privacy.PresidioDetector`
and forces its lazy spaCy/Presidio load by calling ``detect("")`` once, so a
missing NER model surfaces *at startup* rather than on the first unlucky request
(the spec's "startup load, not lazy first-request load" constraint).

On success it records the detector and ``ner_ok = True`` on ``app.state``. If the
model is absent the library raises :class:`~biltiq_privacy.MissingNERModelError`;
rather than crash-loop, the server starts **degraded** — ``ner_ok = False`` with
the remedy logged once — so ``/healthz`` reports 503 and the data endpoints
return 503 until the operator installs the model and restarts. A
degraded-but-observable boundary beats a restart loop.

This is the approved replacement for the deprecated ``@app.on_event("startup")``
hook (approved-versions.md). No PII is logged: the only text handed to the
engine is the empty string, and the exception message is the install hint.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from biltiq_privacy import MissingNERModelError, PresidioDetector
from fastapi import FastAPI

from biltiq_privacy_server.config import Settings

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the detector singleton on startup; start degraded if NER is absent."""
    settings: Settings = app.state.settings
    detector = PresidioDetector(score_threshold=settings.score_threshold)
    try:
        # Force the lazy spaCy/Presidio load now. The empty string carries no
        # PII; the call exists only to trigger (or fail) the model load early.
        detector.detect("")
    except MissingNERModelError as exc:
        app.state.detector = None
        app.state.ner_ok = False
        # `exc` is the install hint (no PII); log the remedy once so the operator
        # sees the one-line fix in the startup log.
        _logger.error("NER model unavailable; starting degraded. Remedy: %s", exc)
    else:
        app.state.detector = detector
        app.state.ner_ok = True
        _logger.info("NER model loaded; detector ready.")
    yield
