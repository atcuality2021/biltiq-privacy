# SPDX-License-Identifier: MIT
"""Lifespan + Depends + factory tests (BILTIQ-013, AC5/AC6/AC7/AC10).

Covers the assembly layer: the startup lifespan (success + degraded), each
``Depends`` provider, and the factory's per-app isolation. Detector model loads
are avoided by swapping the lifespan's ``PresidioDetector`` for a local fake.
"""
from __future__ import annotations

import logging
from typing import Annotated

import pytest
from biltiq_privacy import MissingNERModelError
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from biltiq_privacy_server import models
from biltiq_privacy_server.app import create_app
from biltiq_privacy_server.config import Settings
from biltiq_privacy_server.dependencies import get_detector, get_hmac_key, require_jwt


def _settings(jwt_secret: str, hmac_key: str) -> Settings:
    """Build a Settings directly from the test fixture values."""
    return Settings(
        jwt_secret=jwt_secret,
        hmac_key=hmac_key.encode("utf-8"),
        version="0.1.0",
    )


class _OkDetector:
    """Fake detector whose forced load succeeds (no model)."""

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self.score_threshold = score_threshold

    def detect(self, text: str, language: str = "en") -> list[object]:
        return []


class _MissingModelDetector:
    """Fake detector that raises MissingNERModelError on the forced load."""

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self.score_threshold = score_threshold

    def detect(self, text: str, language: str = "en") -> list[object]:
        raise MissingNERModelError("model gone")


def test_lifespan_sets_detector_and_ner_ok_on_success(
    monkeypatch: pytest.MonkeyPatch, jwt_secret: str, hmac_key: str
) -> None:
    """Startup builds the detector and flags ner_ok True (AC7)."""
    monkeypatch.setattr(
        "biltiq_privacy_server.lifespan.PresidioDetector", _OkDetector
    )
    app = create_app(_settings(jwt_secret, hmac_key))
    with TestClient(app):
        assert app.state.ner_ok is True
        assert isinstance(app.state.detector, _OkDetector)


def test_lifespan_degrades_on_missing_ner_model(
    monkeypatch: pytest.MonkeyPatch,
    jwt_secret: str,
    hmac_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing model degrades the app (ner_ok False) and logs the remedy (AC7)."""
    monkeypatch.setattr(
        "biltiq_privacy_server.lifespan.PresidioDetector", _MissingModelDetector
    )
    app = create_app(_settings(jwt_secret, hmac_key))
    with caplog.at_level(logging.ERROR), TestClient(app):
        assert app.state.ner_ok is False
        assert app.state.detector is None
    messages = [record.getMessage() for record in caplog.records]
    assert any("Remedy" in m for m in messages)
    # The install hint is present; only the empty string was ever processed (no PII).
    assert any("spacy download" in m for m in messages)


def test_get_detector_raises_when_degraded(jwt_secret: str, hmac_key: str) -> None:
    """get_detector signals 503 via the handler when the server is degraded (AC7)."""
    app = create_app(_settings(jwt_secret, hmac_key))
    # Set degraded state directly; without `with`, the lifespan does not run.
    app.state.ner_ok = False
    app.state.detector = None

    @app.get("/_needs_detector")
    def _route(detector: Annotated[object, Depends(get_detector)]) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/_needs_detector")
    assert response.status_code == 503
    assert response.json()["code"] == "ner_model_unavailable"


def test_require_jwt_rejects_missing_bearer(jwt_secret: str, hmac_key: str) -> None:
    """No Authorization header -> 401 (HTTPBearer auto_error=False path, AC5)."""
    app = create_app(_settings(jwt_secret, hmac_key))

    @app.get("/_protected")
    def _route(claims: Annotated[dict, Depends(require_jwt)]) -> dict[str, object]:
        return {"sub": claims["sub"]}

    response = TestClient(app).get("/_protected")
    assert response.status_code == 401


def test_require_jwt_accepts_valid_token(
    jwt_secret: str, hmac_key: str, valid_token: str
) -> None:
    """A valid Bearer token passes and the claims reach the handler (AC5)."""
    app = create_app(_settings(jwt_secret, hmac_key))

    @app.get("/_protected")
    def _route(claims: Annotated[dict, Depends(require_jwt)]) -> dict[str, object]:
        return {"sub": claims["sub"]}

    response = TestClient(app).get(
        "/_protected", headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 200
    assert response.json()["sub"] == "test-client"


def test_get_hmac_key_returns_bytes_not_in_any_response(
    jwt_secret: str, hmac_key: str
) -> None:
    """get_hmac_key returns the key as bytes; no wire model exposes it (AC6)."""
    key = get_hmac_key(_settings(jwt_secret, hmac_key))
    assert isinstance(key, bytes)
    assert key == hmac_key.encode("utf-8")

    wire_fields: set[str] = set()
    for name in dir(models):
        obj = getattr(models, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            wire_fields |= set(obj.model_fields)
    assert "hmac_key" not in wire_fields
    assert "key" not in wire_fields


def test_create_app_builds_isolated_instances(jwt_secret: str, hmac_key: str) -> None:
    """Two factory calls share no app.state (AC10)."""
    app1 = create_app(_settings(jwt_secret, hmac_key))
    app2 = create_app(_settings(jwt_secret, hmac_key))
    assert app1 is not app2
    app1.state.marker = "only-on-app1"
    assert not hasattr(app2.state, "marker")
    assert app1.state.settings is not app2.state.settings


def test_fastapi_client_seam_starts_without_model_load(
    fastapi_client: TestClient,
) -> None:
    """The shared client fixture boots via the fake-detector seam (AC10).

    Exercising the lifespan with the fake means ``app.state`` is populated as in
    production but no spaCy/Presidio model is loaded — the contract the endpoint
    tests (Step 5) rely on.
    """
    app = fastapi_client.app
    assert app.state.ner_ok is True
    assert type(app.state.detector).__name__ == "FakeDetector"
