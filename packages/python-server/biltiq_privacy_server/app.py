# SPDX-License-Identifier: MIT
"""Application factory: assemble settings, lifespan, handlers (BILTIQ-013).

``create_app(settings)`` returns a fully-wired FastAPI instance. All state lives
on the returned app — ``app.state.settings`` plus the lifespan-built detector —
so each app is **isolated**: tests build their own instance with deterministic
settings and no global leaks (AC10, design alternative #2).

There is deliberately **no module-level ``app``** here yet: a module-level
instance would call :func:`~biltiq_privacy_server.config.load_settings` at import
time and break the env-free import contract (and the import probe). The CLI
(Step 6) constructs the app via this factory. Routers are added in Step 5; until
then the factory wires settings, the lifespan, and the exception handlers.
"""
from __future__ import annotations

from fastapi import FastAPI

from biltiq_privacy_server import __version__
from biltiq_privacy_server.config import Settings
from biltiq_privacy_server.errors import register_exception_handlers
from biltiq_privacy_server.lifespan import lifespan


def create_app(settings: Settings) -> FastAPI:
    """Build and return a fully-wired FastAPI app for the given ``settings``."""
    app = FastAPI(
        title="biltiq-privacy-server",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_exception_handlers(app)
    return app
