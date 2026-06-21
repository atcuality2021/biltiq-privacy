# SPDX-License-Identifier: MIT
"""Config fast-fail tests (BILTIQ-013, AC5/AC6).

Covers the startup contract: missing secrets and short HMAC keys must raise
``RuntimeError`` before the app can serve, and the HMAC floor is measured in
bytes (post utf-8), not characters.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from biltiq_privacy_server.config import Settings, load_settings


def test_missing_jwt_secret_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, hmac_key: str
) -> None:
    """No BILTIQ_JWT_SECRET → RuntimeError naming the var (AC5)."""
    monkeypatch.delenv("BILTIQ_JWT_SECRET", raising=False)
    monkeypatch.setenv("BILTIQ_HMAC_KEY", hmac_key)
    with pytest.raises(RuntimeError, match="BILTIQ_JWT_SECRET"):
        load_settings()


def test_missing_hmac_key_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, jwt_secret: str
) -> None:
    """No BILTIQ_HMAC_KEY → RuntimeError naming the var (AC6)."""
    monkeypatch.setenv("BILTIQ_JWT_SECRET", jwt_secret)
    monkeypatch.delenv("BILTIQ_HMAC_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BILTIQ_HMAC_KEY"):
        load_settings()


def test_hmac_key_under_32_bytes_raises(
    monkeypatch: pytest.MonkeyPatch, jwt_secret: str
) -> None:
    """A 31-byte key is rejected; a 32-byte key constructs (AC6 boundary)."""
    monkeypatch.setenv("BILTIQ_JWT_SECRET", jwt_secret)

    monkeypatch.setenv("BILTIQ_HMAC_KEY", "a" * 31)
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        load_settings()

    monkeypatch.setenv("BILTIQ_HMAC_KEY", "a" * 32)
    settings = load_settings()
    assert settings.hmac_key == b"a" * 32


def test_hmac_key_length_measured_post_utf8_encode(
    monkeypatch: pytest.MonkeyPatch, jwt_secret: str
) -> None:
    """The floor is byte length, not character count.

    11 euro signs are 11 characters but 33 bytes in utf-8 — accepted, proving
    the validator counts encoded bytes (would be rejected if it counted chars).
    """
    monkeypatch.setenv("BILTIQ_JWT_SECRET", jwt_secret)
    multibyte_key = "€" * 11  # 11 chars, 33 bytes
    assert len(multibyte_key) < 32 < len(multibyte_key.encode("utf-8"))
    monkeypatch.setenv("BILTIQ_HMAC_KEY", multibyte_key)
    settings = load_settings()
    assert settings.hmac_key == multibyte_key.encode("utf-8")


def test_settings_is_frozen(jwt_secret: str, hmac_key: str) -> None:
    """A constructed Settings cannot be mutated (secrets are immutable)."""
    settings = Settings(
        jwt_secret=jwt_secret,
        hmac_key=hmac_key.encode("utf-8"),
        version="0.1.0",
    )
    with pytest.raises(ValidationError):
        settings.jwt_secret = "mutated"  # type: ignore[misc]  # frozen-model guard under test
