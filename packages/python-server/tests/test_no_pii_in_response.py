# SPDX-License-Identifier: MIT
"""No-raw-PII guarantee for /anonymize (BILTIQ-013, R3/AC10).

A synthetic Indian-PII input must not have its raw value surface in the
tamper-evident audit row's payload (counts + SHA-256 commitments only) nor in
any captured log record (the server logs no request bodies). The detection list
intentionally carries span text — that is the detector contract — so the
assertions target the audit_row payload and the log stream, per the dev ruling.
"""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from biltiq_privacy_server.dependencies import get_detector

#: A synthetic phone number that must never appear in the chain or the logs.
_SYNTHETIC_PHONE = "9876543210"
_SAMPLE_TEXT = f"Call Ravi on {_SYNTHETIC_PHONE}."


class _OneSpanDetector:
    """Fake detector flagging the synthetic phone span (no model load)."""

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self.score_threshold = score_threshold

    def detect(self, text: str, language: str = "en") -> list[dict[str, object]]:
        return [
            {
                "entity_type": "IN_PHONE",
                "text": _SYNTHETIC_PHONE,
                "start": 13,
                "end": 23,
                "score": 0.85,
                "source": "presidio",
            }
        ]


def test_raw_pii_absent_from_audit_row_and_logs(
    fastapi_client: TestClient,
    valid_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The synthetic phone never reaches the audit row payload or the logs (AC10)."""
    fastapi_client.app.dependency_overrides[get_detector] = _OneSpanDetector
    with caplog.at_level(logging.DEBUG):
        resp = fastapi_client.post(
            "/anonymize",
            json={"text": _SAMPLE_TEXT},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
    assert resp.status_code == 200

    payload = resp.json()["audit_row"]["payload"]
    assert _SYNTHETIC_PHONE not in json.dumps(payload)

    log_blob = "\n".join(record.getMessage() for record in caplog.records)
    assert _SYNTHETIC_PHONE not in log_blob
