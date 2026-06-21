# SPDX-License-Identifier: MIT
"""POST /validate endpoint tests (BILTIQ-013, AC3/AC5).

Covers full-report serialisation, the server-supplied generated_at default, the
unknown-regime 422 path, and the JWT gate. /validate runs no detector, but the
healthy fastapi_client seam keeps the router-level readiness gate satisfied.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

_DETECTIONS: list[dict[str, object]] = [
    {
        "entity_type": "IN_PHONE",
        "text": "9876543210",
        "start": 13,
        "end": 23,
        "score": 0.85,
        "source": "presidio",
    }
]

_AUDIT_RECORDS: list[dict[str, object]] = [
    {
        "entity_type": "IN_PHONE",
        "pseudonym_token": "[IN_PHONE_a1b2c3d4]",
        "position_start": 13,
        "position_end": 23,
        "confidence": 0.85,
    }
]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _body(regime: str = "DPDP-2023") -> dict[str, object]:
    return {
        "original_text": "Call Ravi on 9876543210.",
        "anonymised_text": "Call Ravi on [IN_PHONE_a1b2c3d4].",
        "detections": _DETECTIONS,
        "audit_records": _AUDIT_RECORDS,
        "generated_at": "2026-06-21T07:00:00+00:00",
        "regime": regime,
    }


def test_validate_full_report(fastapi_client: TestClient, valid_token: str) -> None:
    """A known regime returns its full ComplianceReport (AC3)."""
    resp = fastapi_client.post(
        "/validate", json=_body(), headers=_auth(valid_token)
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["regime_id"] == "DPDP-2023"
    assert isinstance(report["compliant"], bool)
    assert report["checks"]
    assert "/" in report["score"]
    assert report["generated_at"] == "2026-06-21T07:00:00+00:00"


def test_validate_generated_at_default_applied(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """An omitted generated_at is filled by the server (AC3)."""
    body = _body()
    del body["generated_at"]
    resp = fastapi_client.post("/validate", json=body, headers=_auth(valid_token))
    assert resp.status_code == 200
    assert resp.json()["generated_at"]  # non-empty server-supplied timestamp


def test_validate_unknown_regime_returns_422(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """An unknown regime id -> 422 unknown_regime (AC3)."""
    resp = fastapi_client.post(
        "/validate", json=_body(regime="NOT-A-REGIME"), headers=_auth(valid_token)
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "unknown_regime"


def test_validate_missing_jwt_returns_401(fastapi_client: TestClient) -> None:
    """No Authorization header -> 401 (router-level require_jwt, AC5)."""
    resp = fastapi_client.post("/validate", json=_body())
    assert resp.status_code == 401
