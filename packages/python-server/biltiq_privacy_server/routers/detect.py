# SPDX-License-Identifier: MIT
"""POST /detect — run the detector, return the spans (BILTIQ-013, AC1).

A translate-and-delegate handler: it validates the body, runs the injected
detector singleton (or a fresh threshold-overridden detector when the request
supplies ``score_threshold``), and projects each library
:class:`~biltiq_privacy.DetectedEntity` into a
:class:`~biltiq_privacy_server.models.DetectionModel`. All detection logic lives
in ``biltiq_privacy`` — the server contributes none.

The handler is a plain ``def`` (not ``async def``): the detector call is a
synchronous, CPU/IO-bound model invocation, so FastAPI runs it in its worker
threadpool rather than blocking the event loop (design alternative #7).
Authentication is enforced at the *router* level, so every route added here is
JWT-gated by construction (AC5); the same router-level gate also raises 503 when
the engine failed to load at startup (AC7), because ``get_detector`` is the
shared degraded gate.
"""
from __future__ import annotations

from typing import Annotated

from biltiq_privacy import Detector, PresidioDetector
from fastapi import APIRouter, Depends

from biltiq_privacy_server.dependencies import get_detector, require_jwt
from biltiq_privacy_server.models import DetectionModel, DetectRequest, DetectResponse

router = APIRouter(dependencies=[Depends(require_jwt)])


@router.post("/detect", response_model=DetectResponse)
def detect(
    body: DetectRequest,
    detector: Annotated[Detector, Depends(get_detector)],
) -> DetectResponse:
    """Detect PII spans in ``body.text`` (AC1).

    Empty / whitespace-only text short-circuits to an empty result with no
    engine call, mirroring the library's own ``text.strip()`` guard. A
    request-supplied ``score_threshold`` overrides the server default by running
    a detector tuned to it; the startup singleton keeps the settings threshold
    for ``/anonymize``. Building that override detector rebuilds its engine — a
    deliberate, override-only cost; the common path reuses the singleton.
    """
    if not body.text.strip():
        return DetectResponse(detections=[], count=0)

    active = detector
    if body.score_threshold is not None:
        active = PresidioDetector(score_threshold=body.score_threshold)

    spans = active.detect(body.text, language=body.language)
    detections = [DetectionModel.model_validate(span) for span in spans]
    return DetectResponse(detections=detections, count=len(detections))
