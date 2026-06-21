# SPDX-License-Identifier: MIT
"""Uniform error envelope + library-exception → HTTP mapping (BILTIQ-013, AC11).

Every error the server emits is shaped ``{"detail": str, "code": str}`` (the
:class:`~biltiq_privacy_server.models.ErrorResponse` wire model), so a polyglot
SDK parses one error shape across all endpoints.
``register_exception_handlers`` installs the mapping once on the app:

==========================  ====  ======================================
Exception                   HTTP  Meaning
==========================  ====  ======================================
``MissingNERModelError``    503   engine degraded; restart needed (AC7)
``HMACKeyRequiredError``    500   defence-in-depth — see note below
``UnknownRegimeError``      422   client named an unknown regime (AC3)
``RequestValidationError``  422   body validation, reshaped to the envelope
==========================  ====  ======================================

The ``HMACKeyRequiredError`` handler is defence-in-depth: the key is validated
at startup (``config.load_settings``), so a missing key should never reach a
handler in production. Keeping the handler turns the unreachable case into a
clean ``500`` envelope rather than an unhandled stack trace (dev ruling).

Detail strings are operator/client-safe — they never echo PII, the token, or
the secret.
"""
from __future__ import annotations

from biltiq_privacy import HMACKeyRequiredError, MissingNERModelError
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

#: starlette 1.0 renamed ``HTTP_422_UNPROCESSABLE_ENTITY`` ->
#: ``HTTP_422_UNPROCESSABLE_CONTENT`` (deprecating the old name), but the new
#: name is absent on the ``fastapi>=0.110`` floor this package supports. The
#: integer is stable across the whole supported range, so bind it once here and
#: avoid both the deprecation warning and the missing-constant break (AP #9).
_HTTP_422_UNPROCESSABLE = 422


class UnknownRegimeError(Exception):
    """Raised when a request names a regime id absent from the registry (AC3).

    Server-local: the library has no concept of a regime registry, so this type
    lives here and is mapped to HTTP 422 by :func:`register_exception_handlers`.
    """


def _envelope(*, detail: str, code: str, status_code: int) -> JSONResponse:
    """Build the uniform ``{"detail","code"}`` JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install the exception → uniform-envelope handlers on ``app`` (AC11)."""

    @app.exception_handler(MissingNERModelError)
    async def _handle_missing_ner(
        request: Request, exc: MissingNERModelError
    ) -> JSONResponse:
        return _envelope(
            detail=(
                "NER model is not loaded; the server is running degraded. "
                "Install the model and restart."
            ),
            code="ner_model_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @app.exception_handler(HMACKeyRequiredError)
    async def _handle_hmac_required(
        request: Request, exc: HMACKeyRequiredError
    ) -> JSONResponse:
        return _envelope(
            detail="Server pseudonymisation key is misconfigured.",
            code="hmac_key_required",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(UnknownRegimeError)
    async def _handle_unknown_regime(
        request: Request, exc: UnknownRegimeError
    ) -> JSONResponse:
        # `exc` is server-built from the regime id only (no PII), so echoing it
        # tells the client which regimes are known.
        return _envelope(
            detail=str(exc),
            code="unknown_regime",
            status_code=_HTTP_422_UNPROCESSABLE,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _envelope(
            detail="Request body failed validation.",
            code="validation_error",
            status_code=_HTTP_422_UNPROCESSABLE,
        )
