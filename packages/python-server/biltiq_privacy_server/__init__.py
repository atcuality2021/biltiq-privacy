# SPDX-License-Identifier: MIT
"""biltiq-privacy-server — FastAPI sidecar over the biltiq-privacy engine.

Exposes ``/detect``, ``/anonymize``, ``/validate`` (JWT-gated) and an
unauthenticated ``/healthz`` probe over the engine (BILTIQ-013). The ASGI app is
assembled by :func:`biltiq_privacy_server.app.create_app`; importing this
package stays env-free — only importing ``biltiq_privacy_server.app`` reads the
runtime secrets.
"""
from __future__ import annotations

from importlib.metadata import version

__version__: str = version("biltiq-privacy-server")

__all__ = ["__version__"]
