# SPDX-License-Identifier: MIT
"""Committed-OpenAPI drift gate (BILTIQ-013, AC9).

The checked-in ``openapi.json`` is the contract the v0.1.1+ native SDK generator
consumes, so it must stay in lock-step with the live app. These tests fail CI if
a handler or model change is not re-exported (regenerate via the README
one-liner). The comparison is on *parsed* dicts, so cosmetic formatting of the
committed file (indent / key order) never triggers a false drift — only a real
schema change does.

The export is settings-independent: ``Settings`` only ever reaches ``app.state``
and never the schema, so any valid ``Settings`` reproduces the committed
contract — and no secret can leak into ``openapi.json`` (AC6).
"""
from __future__ import annotations

import json
from pathlib import Path

from biltiq_privacy_server import __version__
from biltiq_privacy_server.app import create_app
from biltiq_privacy_server.config import Settings

#: The committed contract lives at the package root, beside pyproject.toml.
_COMMITTED_OPENAPI = Path(__file__).resolve().parent.parent / "openapi.json"

#: Deterministic export settings — values never enter the schema (settings live
#: on ``app.state`` only), so this reproduces the committed contract exactly.
_EXPORT_SETTINGS = Settings(
    jwt_secret="openapi-export", hmac_key=b"0" * 32, version=__version__
)


def _live_schema() -> dict[str, object]:
    """Return the OpenAPI schema the running app would serve."""
    return create_app(_EXPORT_SETTINGS).openapi()


def test_live_openapi_matches_committed() -> None:
    """The live schema deep-equals the committed openapi.json (AC9 drift gate)."""
    committed = json.loads(_COMMITTED_OPENAPI.read_text(encoding="utf-8"))
    assert _live_schema() == committed, (
        "openapi.json is stale — regenerate it with the README one-liner and "
        "commit the result (BILTIQ-013 AC9)."
    )


def test_openapi_lists_all_four_paths() -> None:
    """All four endpoints are present with the right HTTP methods (AC9)."""
    paths = _live_schema()["paths"]
    assert isinstance(paths, dict)
    assert "post" in paths["/detect"]
    assert "post" in paths["/anonymize"]
    assert "post" in paths["/validate"]
    assert "get" in paths["/healthz"]
