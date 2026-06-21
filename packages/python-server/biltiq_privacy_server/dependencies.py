# SPDX-License-Identifier: MIT
"""Depends() providers: auth, settings, HMAC key, detector (BILTIQ-013).

Every per-request dependency reads from ``app.state`` (populated by the factory
and the lifespan) or from the validated bearer credentials — **never from the
request body**. The HMAC key in particular flows only through
:func:`get_hmac_key` (AC6): it is never a body field, never serialised into a
response, and never logged.

Dependencies use the ``Annotated[T, Depends(...)]`` form (current FastAPI style)
so the injected types are explicit and the lint stays clean.
"""
from __future__ import annotations

from typing import Annotated

from biltiq_privacy import Detector, MissingNERModelError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from biltiq_privacy_server.auth import verify_token
from biltiq_privacy_server.config import Settings

#: ``auto_error=False`` so a missing/invalid Authorization header yields ``None``
#: and we raise our own uniform 401 (with the WWW-Authenticate challenge), rather
#: than HTTPBearer's default 403.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_settings(request: Request) -> Settings:
    """Return the per-app :class:`Settings` the factory cached on ``app.state``."""
    settings: Settings = request.app.state.settings
    return settings


def get_hmac_key(settings: Annotated[Settings, Depends(get_settings)]) -> bytes:
    """Return the HMAC pseudonymisation key (AC6).

    The key reaches request handling only through this provider — never via a
    request body or a response model — so the secret stays server-side.
    """
    return settings.hmac_key


def get_detector(request: Request) -> Detector:
    """Return the detector singleton, or signal 503 when the server is degraded.

    Raises:
        MissingNERModelError: when the NER model failed to load at startup
            (``ner_ok`` is ``False``). The registered handler maps it to 503,
            so every data endpoint depending on the detector returns 503 until a
            restart with the model present (AC7).
    """
    if not request.app.state.ner_ok:
        raise MissingNERModelError(
            "Detector is unavailable; the server started without the NER model."
        )
    detector: Detector = request.app.state.detector
    return detector


def require_jwt(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, object]:
    """Verify the Bearer token and return its claims, or raise 401 (AC5)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers=_UNAUTHORIZED_HEADERS,
        )
    settings: Settings = request.app.state.settings
    return verify_token(credentials.credentials, secret=settings.jwt_secret)
