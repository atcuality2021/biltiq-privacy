# SPDX-License-Identifier: MIT
"""Exception-handler mapping tests (BILTIQ-013, AC7/AC11).

These exercise ``register_exception_handlers`` in isolation: a tiny throwaway
app with one route per mapped exception, driven by ``TestClient``. The point is
the contract — every handler returns the uniform ``{"detail","code"}`` envelope
with the correct status code — not any real endpoint behaviour.
"""
from __future__ import annotations

import pytest
from biltiq_privacy import HMACKeyRequiredError, MissingNERModelError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from biltiq_privacy_server.errors import (
    UnknownRegimeError,
    register_exception_handlers,
)


class _Body(BaseModel):
    """Minimal body model to trigger RequestValidationError on a bad payload."""

    value: int


def _probe_app() -> FastAPI:
    """A throwaway app: one route per mapped exception, handlers installed."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-ner")
    def _raise_ner() -> None:
        raise MissingNERModelError("model gone")

    @app.get("/raise-hmac")
    def _raise_hmac() -> None:
        raise HMACKeyRequiredError("key missing")

    @app.get("/raise-regime")
    def _raise_regime() -> None:
        raise UnknownRegimeError("Unknown regime 'X'. Known regimes: DPDP-2023.")

    @app.post("/needs-body")
    def _needs_body(body: _Body) -> dict[str, int]:
        return {"value": body.value}

    return app


@pytest.fixture
def client() -> TestClient:
    """A TestClient over the throwaway handler-probe app."""
    return TestClient(_probe_app())


def test_error_envelope_shape(client: TestClient) -> None:
    """Every handler returns exactly the {"detail","code"} envelope (AC11)."""
    for method, path in [
        ("get", "/raise-ner"),
        ("get", "/raise-hmac"),
        ("get", "/raise-regime"),
    ]:
        response = getattr(client, method)(path)
        body = response.json()
        assert set(body) == {"detail", "code"}
        assert isinstance(body["detail"], str)
        assert isinstance(body["code"], str)

    # RequestValidationError path: wrong type for `value`.
    invalid = client.post("/needs-body", json={"value": "not-an-int"})
    assert set(invalid.json()) == {"detail", "code"}


def test_missing_ner_maps_503_unknown_regime_422(client: TestClient) -> None:
    """MissingNERModelError -> 503; UnknownRegimeError + validation -> 422 (AC7/AC11)."""
    ner = client.get("/raise-ner")
    assert ner.status_code == 503
    assert ner.json()["code"] == "ner_model_unavailable"

    regime = client.get("/raise-regime")
    assert regime.status_code == 422
    assert regime.json()["code"] == "unknown_regime"
    # The detail names the known regimes (no PII), aiding the client.
    assert "DPDP-2023" in regime.json()["detail"]

    validation = client.post("/needs-body", json={"value": "not-an-int"})
    assert validation.status_code == 422
    assert validation.json()["code"] == "validation_error"


def test_hmac_key_required_maps_500(client: TestClient) -> None:
    """HMACKeyRequiredError -> 500 defence-in-depth handler (AC11)."""
    response = client.get("/raise-hmac")
    assert response.status_code == 500
    assert response.json()["code"] == "hmac_key_required"
    # The secret/key value never appears in the envelope.
    assert "key missing" not in response.json()["detail"]
