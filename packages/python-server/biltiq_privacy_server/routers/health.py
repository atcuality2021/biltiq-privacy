# SPDX-License-Identifier: MIT
"""GET /healthz — unauthenticated liveness/readiness probe (BILTIQ-013, AC4).

Returns 200 ``{"status":"ok","version":...}`` when the NER model loaded at
startup (``app.state.ner_ok``), or 503 ``{"status":"degraded","reason":...}``
when it did not — the same degraded signal the data endpoints surface via
``get_detector`` (AC7), exposed here as a probe an orchestrator can poll.

No authentication: a health probe must work before any token is issued, so this
router declares no ``require_jwt`` dependency (AC4; AC5 scopes auth to the three
data endpoints). ``ner_ok`` is read defensively (``getattr`` defaulting to
``False``) so a probe that arrives before startup finished reports *degraded*
rather than crashing.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from biltiq_privacy_server.config import Settings
from biltiq_privacy_server.models import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz(request: Request, response: Response) -> HealthResponse:
    """Report engine readiness: 200 when loaded, 503 when degraded (AC4)."""
    settings: Settings = request.app.state.settings
    ner_ok: bool = getattr(request.app.state, "ner_ok", False)
    if ner_ok:
        return HealthResponse(status="ok", version=settings.version)

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="degraded",
        version=settings.version,
        reason="NER model not loaded",
    )
