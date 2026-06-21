# SPDX-License-Identifier: MIT
"""POST /anonymize endpoint tests (BILTIQ-013, AC2/AC6).

Covers full AnonymiseResult serialisation, the two server-supplied defaults
(generated_at, prev_hash), the regime on/off branches, the JWT gate, and the
AC6/R3 secret-and-PII-surface guarantees. A local fake detector yields a fixed
span so the full pipeline (pseudonymise → generalise → chain) runs with no model
load.
"""
from __future__ import annotations

import logging

import pytest
from biltiq_privacy import GENESIS_PREV_HASH
from fastapi.testclient import TestClient

from biltiq_privacy_server.dependencies import get_detector

_PHONE_SPAN: dict[str, object] = {
    "entity_type": "IN_PHONE",
    "text": "9876543210",
    "start": 13,
    "end": 23,
    "score": 0.85,
    "source": "presidio",
}

_SAMPLE_TEXT = "Call Ravi on 9876543210."


class _OneSpanDetector:
    """Fake detector returning one fixed span (no model load)."""

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self.score_threshold = score_threshold

    def detect(self, text: str, language: str = "en") -> list[dict[str, object]]:
        return [dict(_PHONE_SPAN)]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _post(client: TestClient, token: str, **body: object) -> object:
    client.app.dependency_overrides[get_detector] = _OneSpanDetector
    return client.post(
        "/anonymize", json={"text": _SAMPLE_TEXT, **body}, headers=_auth(token)
    )


def test_anonymize_full_serialisation(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """Every AnonymiseResult field is serialised, including the audit row (AC2)."""
    resp = _post(fastapi_client, valid_token)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["anonymised_text"], str)
    assert body["detections"][0]["entity_type"] == "IN_PHONE"
    assert body["audit_records"][0]["pseudonym_token"]
    assert body["audit_row"]["prev_hash"] == GENESIS_PREV_HASH
    assert body["audit_row"]["hash"]
    assert "generated_at" in body["audit_row"]["payload"]
    assert body["compliance"] is None  # no regime supplied


def test_anonymize_generated_at_default_applied(
    fastapi_client: TestClient,
    valid_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An omitted generated_at is filled by the server's single clock read (AC2)."""
    monkeypatch.setattr(
        "biltiq_privacy_server.routers.anonymize.server_now_iso",
        lambda: "2026-06-21T07:00:00+00:00",
    )
    resp = _post(fastapi_client, valid_token)
    assert resp.status_code == 200
    assert (
        resp.json()["audit_row"]["payload"]["generated_at"]
        == "2026-06-21T07:00:00+00:00"
    )


def test_anonymize_prev_hash_defaults_to_genesis(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """An omitted prev_hash starts a new chain at GENESIS_PREV_HASH (AC2)."""
    resp = _post(fastapi_client, valid_token)
    assert resp.json()["audit_row"]["prev_hash"] == GENESIS_PREV_HASH


def test_anonymize_regime_null_yields_no_compliance(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """regime omitted -> compliance is None (AC2)."""
    resp = _post(fastapi_client, valid_token, regime=None)
    assert resp.json()["compliance"] is None


def test_anonymize_regime_dpdp_yields_report(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """regime='DPDP-2023' -> a populated compliance report (AC2)."""
    resp = _post(fastapi_client, valid_token, regime="DPDP-2023")
    assert resp.status_code == 200
    compliance = resp.json()["compliance"]
    assert compliance is not None
    assert compliance["regime_id"] == "DPDP-2023"
    assert compliance["checks"]
    assert "/" in compliance["score"]  # e.g. "8/8"


def test_anonymize_unknown_regime_returns_422(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """An unknown regime id -> 422 unknown_regime (AC3 envelope reused)."""
    resp = _post(fastapi_client, valid_token, regime="NOPE")
    assert resp.status_code == 422
    assert resp.json()["code"] == "unknown_regime"


def test_anonymize_missing_jwt_returns_401(fastapi_client: TestClient) -> None:
    """No Authorization header -> 401 (router-level require_jwt, AC5)."""
    resp = fastapi_client.post("/anonymize", json={"text": _SAMPLE_TEXT})
    assert resp.status_code == 401


def test_anonymize_does_not_leak_key_or_original_text(
    fastapi_client: TestClient,
    valid_token: str,
    hmac_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The HMAC key never appears in the body/logs; original_text is not echoed (AC6/R3)."""
    with caplog.at_level(logging.DEBUG):
        resp = _post(fastapi_client, valid_token)
    assert resp.status_code == 200
    raw = resp.text
    assert hmac_key not in raw
    assert "hmac_key" not in raw
    assert "original_text" not in resp.json()  # original text is not echoed back
    # The secret must not have reached any log record either.
    assert all(hmac_key not in record.getMessage() for record in caplog.records)
