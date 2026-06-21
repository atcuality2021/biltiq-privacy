# SPDX-License-Identifier: MIT
"""/healthz + degraded-gate tests (BILTIQ-013, AC4/AC7).

``/healthz`` reports 200 when the engine loaded and 503 when it did not, with no
auth required. AC7 requires *all three* data endpoints to return 503 while
degraded; a degraded app (built without running the lifespan) proves the shared
``get_detector`` gate covers /detect, /anonymize, and /validate alike.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from biltiq_privacy_server.app import create_app
from biltiq_privacy_server.config import Settings


def _settings(jwt_secret: str, hmac_key: str) -> Settings:
    return Settings(
        jwt_secret=jwt_secret,
        hmac_key=hmac_key.encode("utf-8"),
        version="0.1.0",
    )


def _degraded_client(jwt_secret: str, hmac_key: str) -> TestClient:
    """An app whose lifespan never ran -> ner_ok False, detector None."""
    app = create_app(_settings(jwt_secret, hmac_key))
    app.state.ner_ok = False
    app.state.detector = None
    # No ``with``: startup is not run, so the engine is never loaded.
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_healthz_ok_needs_no_auth(fastapi_client: TestClient) -> None:
    """A loaded engine reports 200 ok with the version, no token required (AC4)."""
    resp = fastapi_client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["reason"] is None


def test_healthz_degraded_returns_503(jwt_secret: str, hmac_key: str) -> None:
    """A degraded engine reports 503 degraded with a reason (AC4/AC7)."""
    resp = _degraded_client(jwt_secret, hmac_key).get("/healthz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["reason"] == "NER model not loaded"


def test_degraded_detect_returns_503(
    jwt_secret: str, hmac_key: str, valid_token: str
) -> None:
    """/detect returns 503 while the engine is degraded (AC7)."""
    resp = _degraded_client(jwt_secret, hmac_key).post(
        "/detect", json={"text": "Call Ravi on 9876543210."}, headers=_auth(valid_token)
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "ner_model_unavailable"


def test_degraded_anonymize_returns_503(
    jwt_secret: str, hmac_key: str, valid_token: str
) -> None:
    """/anonymize returns 503 while the engine is degraded (AC7)."""
    resp = _degraded_client(jwt_secret, hmac_key).post(
        "/anonymize", json={"text": "Call Ravi on 9876543210."}, headers=_auth(valid_token)
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "ner_model_unavailable"


def test_degraded_validate_returns_503(
    jwt_secret: str, hmac_key: str, valid_token: str
) -> None:
    """/validate returns 503 while the engine is degraded (AC7, "all three")."""
    body = {
        "original_text": "Call Ravi on 9876543210.",
        "anonymised_text": "Call Ravi on [IN_PHONE_x].",
        "detections": [],
        "audit_records": [],
        "regime": "DPDP-2023",
    }
    resp = _degraded_client(jwt_secret, hmac_key).post(
        "/validate", json=body, headers=_auth(valid_token)
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "ner_model_unavailable"
