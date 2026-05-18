# SPDX-License-Identifier: MIT
"""biltiq-privacy-server — FastAPI sidecar over the biltiq-privacy engine.

Pre-implementation scaffold (v0.1.0). Routes /anonymize and /validate
land after the engine ports complete (BILTIQ-002+).
"""
from __future__ import annotations

from importlib.metadata import version

__version__: str = version("biltiq-privacy-server")

__all__ = ["__version__"]
