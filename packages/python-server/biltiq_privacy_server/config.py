# SPDX-License-Identifier: MIT
"""Server configuration: frozen settings + fail-fast secret loading (BILTIQ-013).

`Settings` is a frozen pydantic v2 ``BaseModel`` — deliberately *not*
pydantic-settings, which is not in this repo's stack (docs/architecture/stack.md)
and would add a dependency for two environment reads. ``load_settings()`` reads
the two required secrets from the environment exactly once and raises
``RuntimeError`` if either is missing or the HMAC key is too short. It is called
at import time of the app module, so a misconfigured deployment fails before
uvicorn binds the port (spec AC5/AC6).

Secrets live here and nowhere else: they are injected into request handling via
``Depends`` (see ``dependencies.py``) and never appear in a request/response
model or a log record.
"""
from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from biltiq_privacy_server import __version__

#: Minimum HMAC pseudonymisation-key length, measured **after** utf-8 encoding
#: (256-bit), matching how ``biltiq_privacy.Pseudonymiser`` consumes the key.
_MIN_HMAC_KEY_BYTES = 32

_JWT_SECRET_ENV = "BILTIQ_JWT_SECRET"
_HMAC_KEY_ENV = "BILTIQ_HMAC_KEY"


class Settings(BaseModel):
    """Immutable server settings holding the two runtime secrets.

    Frozen so a handler can never mutate a secret mid-request. Constructed only
    via :func:`load_settings`; tests build it directly with deterministic values.
    """

    model_config = ConfigDict(frozen=True)

    jwt_secret: str
    hmac_key: bytes
    jwt_algorithm: Literal["HS256"] = "HS256"
    score_threshold: float = 0.5
    version: str

    @field_validator("hmac_key")
    @classmethod
    def _hmac_key_min_length(cls, value: bytes) -> bytes:
        """Reject HMAC keys below the 256-bit floor (byte length, post-utf-8)."""
        if len(value) < _MIN_HMAC_KEY_BYTES:
            raise ValueError(
                f"{_HMAC_KEY_ENV} must be at least {_MIN_HMAC_KEY_BYTES} bytes "
                f"(256-bit) after utf-8 encoding; got {len(value)} bytes."
            )
        return value


def load_settings() -> Settings:
    """Read the required secrets from the environment once; fail fast if invalid.

    Returns:
        A frozen :class:`Settings` built from ``BILTIQ_JWT_SECRET`` and
        ``BILTIQ_HMAC_KEY`` (utf-8 encoded to bytes).

    Raises:
        RuntimeError: if either env var is unset/empty, or if the HMAC key is
            shorter than 32 bytes. Raised before the app binds a port so a
            misconfigured deployment never serves traffic.
    """
    jwt_secret = os.environ.get(_JWT_SECRET_ENV)
    if not jwt_secret:
        raise RuntimeError(f"{_JWT_SECRET_ENV} is required but is unset or empty.")

    hmac_key_str = os.environ.get(_HMAC_KEY_ENV)
    if not hmac_key_str:
        raise RuntimeError(f"{_HMAC_KEY_ENV} is required but is unset or empty.")

    try:
        return Settings(
            jwt_secret=jwt_secret,
            hmac_key=hmac_key_str.encode("utf-8"),
            version=__version__,
        )
    except ValidationError as exc:
        # Re-raise as RuntimeError so startup fails with a flat, actionable
        # message rather than a pydantic stack trace. The validator message
        # names the offending env var; the secret value itself is never echoed.
        raise RuntimeError(f"Invalid server configuration: {exc}") from exc
