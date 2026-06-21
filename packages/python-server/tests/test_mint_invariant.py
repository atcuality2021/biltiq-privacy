# SPDX-License-Identifier: MIT
"""Structural verify-only invariant for the mint CLI (BILTIQ-013a, AC6).

Two complementary checks, neither subsuming the other:

1. **Isolation** — ``jwt.encode`` appears in exactly one production module
   (``mint.py``). A source grep, immune to import-order/``sys.modules`` pollution.
2. **Unreachability** — importing the ASGI app in a *fresh* interpreter never
   loads ``mint``. Run in a subprocess so a prior in-process import of ``mint``
   (e.g. by ``test_mint.py``) cannot pollute the result.

Together they prove the running server's request-handling runtime never reaches
``jwt.encode`` — token issuance lives only in the operator tool (ADR-0007).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import biltiq_privacy_server

_PKG_DIR = Path(biltiq_privacy_server.__file__).resolve().parent


def test_jwt_encode_isolated_to_mint_module() -> None:
    """Only mint.py contains a jwt.encode call across the production package."""
    encoders = sorted(
        path.relative_to(_PKG_DIR).as_posix()
        for path in _PKG_DIR.rglob("*.py")
        if "jwt.encode" in path.read_text(encoding="utf-8")
    )
    assert encoders == ["mint.py"], f"jwt.encode found outside mint.py: {encoders}"


def test_app_import_graph_does_not_load_mint() -> None:
    """A fresh interpreter importing app:app never imports the mint module."""
    probe = (
        "import biltiq_privacy_server.app\n"
        "import sys\n"
        "mod = 'biltiq_privacy_server.mint'\n"
        "assert mod not in sys.modules, 'mint is reachable from the app import graph'\n"
    )
    env = {
        **os.environ,
        # app.py builds the app at import (load_settings fail-fast) — both secrets
        # must be present. Obvious non-secrets; the HMAC key clears the 32-byte floor.
        "BILTIQ_JWT_SECRET": "invariant-probe-secret",
        "BILTIQ_HMAC_KEY": "invariant-probe-hmac-key-0123456789ab",
    }
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
