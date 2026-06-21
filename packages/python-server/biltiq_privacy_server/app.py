# SPDX-License-Identifier: MIT
"""Application factory + module-level ASGI app (BILTIQ-013).

``create_app(settings)`` returns a fully-wired FastAPI instance: settings on
``app.state``, the startup lifespan, the exception handlers, and the four
routers (``/detect``, ``/anonymize``, ``/validate``, ``/healthz``). Every app is
isolated — tests build their own instance with deterministic settings, so no
global state leaks across tests (AC10).

``app = create_app(load_settings())`` at module scope is the ASGI target uvicorn
imports (``biltiq_privacy_server.app:app``, used by the Step 6 CLI). It reads the
two required secrets from the environment at import, so a misconfigured
deployment fails fast — before uvicorn binds the port (AC5/AC6) — rather than on
the first request. Importing the *package* ``biltiq_privacy_server`` stays
env-free (its ``__init__`` does not import this module); only importing
``biltiq_privacy_server.app`` requires the secrets, which is exactly the
serve-time contract.
"""
from __future__ import annotations

from fastapi import FastAPI

from biltiq_privacy_server import __version__
from biltiq_privacy_server.config import Settings, load_settings
from biltiq_privacy_server.errors import register_exception_handlers
from biltiq_privacy_server.lifespan import lifespan
from biltiq_privacy_server.routers import anonymize, detect, health, validate


def create_app(settings: Settings) -> FastAPI:
    """Build and return a fully-wired FastAPI app for the given ``settings``."""
    app = FastAPI(
        title="biltiq-privacy-server",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_exception_handlers(app)
    app.include_router(detect.router)
    app.include_router(anonymize.router)
    app.include_router(validate.router)
    app.include_router(health.router)
    return app


#: ASGI target for uvicorn (``biltiq_privacy_server.app:app``). Reads the
#: required secrets from the environment at import — fail-fast startup (AC5/AC6).
app = create_app(load_settings())
