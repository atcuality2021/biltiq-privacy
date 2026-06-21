# SPDX-License-Identifier: MIT
"""POST /detect endpoint tests (BILTIQ-013, AC1/AC5).

Exercises the happy path, the per-request threshold override, the empty-text
short-circuit, and the two JWT rejection paths. Detector behaviour is supplied
by local fakes (via ``dependency_overrides`` or by monkeypatching the router's
``PresidioDetector``) so no spaCy/Presidio model is loaded.
"""
from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from biltiq_privacy_server.dependencies import get_detector

#: A single synthetic IN_PHONE span aligned to "Call Ravi on 9876543210."
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
    """Fake detector returning one fixed span; honours the constructor shape."""

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self.score_threshold = score_threshold

    def detect(self, text: str, language: str = "en") -> list[dict[str, object]]:
        return [dict(_PHONE_SPAN)]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_detect_happy_path(fastapi_client: TestClient, valid_token: str) -> None:
    """A detected span is serialised and counted (AC1)."""
    fastapi_client.app.dependency_overrides[get_detector] = _OneSpanDetector
    resp = fastapi_client.post(
        "/detect", json={"text": _SAMPLE_TEXT}, headers=_auth(valid_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    span = body["detections"][0]
    assert span["entity_type"] == "IN_PHONE"
    assert span["source"] == "presidio"
    assert span["start"] == 13


def test_detect_threshold_override_builds_tuned_detector(
    fastapi_client: TestClient,
    valid_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request score_threshold builds a detector tuned to it (AC1)."""
    seen: dict[str, float] = {}

    class _Recording:
        def __init__(self, *, score_threshold: float = 0.5) -> None:
            seen["threshold"] = score_threshold

        def detect(self, text: str, language: str = "en") -> list[dict[str, object]]:
            return [dict(_PHONE_SPAN)]

    monkeypatch.setattr(
        "biltiq_privacy_server.routers.detect.PresidioDetector", _Recording
    )
    resp = fastapi_client.post(
        "/detect",
        json={"text": _SAMPLE_TEXT, "score_threshold": 0.3},
        headers=_auth(valid_token),
    )
    assert resp.status_code == 200
    assert seen["threshold"] == 0.3
    assert resp.json()["count"] == 1


def test_detect_empty_text_short_circuits(
    fastapi_client: TestClient, valid_token: str
) -> None:
    """Whitespace-only text returns an empty result with no engine call (AC1)."""
    # Even though the override would yield a span, empty text short-circuits.
    fastapi_client.app.dependency_overrides[get_detector] = _OneSpanDetector
    resp = fastapi_client.post(
        "/detect", json={"text": "   "}, headers=_auth(valid_token)
    )
    assert resp.status_code == 200
    assert resp.json() == {"detections": [], "count": 0}


def test_detect_missing_jwt_returns_401(fastapi_client: TestClient) -> None:
    """No Authorization header -> 401 (router-level require_jwt, AC5)."""
    resp = fastapi_client.post("/detect", json={"text": _SAMPLE_TEXT})
    assert resp.status_code == 401


def test_detect_invalid_jwt_returns_401(
    fastapi_client: TestClient, token_minter: Callable[..., str]
) -> None:
    """A token signed with the wrong secret -> 401 (AC5)."""
    bad = token_minter(secret="a-different-secret-at-least-32-bytes-long!")
    resp = fastapi_client.post(
        "/detect", json={"text": _SAMPLE_TEXT}, headers=_auth(bad)
    )
    assert resp.status_code == 401
