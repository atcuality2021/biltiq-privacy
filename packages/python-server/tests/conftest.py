# SPDX-License-Identifier: MIT
"""Shared test fixtures for the FastAPI sidecar (BILTIQ-013).

Secrets here are obvious non-secrets, used only to drive tests. This module is
the **only** place ``jwt.encode`` is called — production code is verify-only
(ADR-0007); the server never mints tokens.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest

#: Deterministic test secret for HS256 signing/verification.
TEST_JWT_SECRET = "test-jwt-secret-not-a-real-secret"
#: 34 bytes of ASCII — clears the 32-byte (256-bit) HMAC floor (AC6).
TEST_HMAC_KEY = "test-hmac-key-0123456789abcdef-ok!"


def _mint_token(
    *,
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
    expires_in: timedelta = timedelta(minutes=5),
    subject: str = "test-client",
) -> str:
    """Mint a signed JWT for tests. The single ``jwt.encode`` call in the suite.

    Defaults produce a valid short-lived HS256 token; callers override
    ``secret`` / ``algorithm`` / ``expires_in`` to exercise the rejection paths.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


# --- Fixtures (consumed by directory proximity; no cross-package import) ------
# The repo has two `tests/` directories (python-core, python-server) that both
# map to the `tests` package, so `from tests.conftest import ...` is ambiguous.
# Exposing shared values as fixtures sidesteps that — pytest binds the conftest
# nearest the test file.


@pytest.fixture
def jwt_secret() -> str:
    """The deterministic test JWT secret."""
    return TEST_JWT_SECRET


@pytest.fixture
def hmac_key() -> str:
    """The deterministic test HMAC key (>= 32 bytes)."""
    return TEST_HMAC_KEY


@pytest.fixture
def token_minter() -> Callable[..., str]:
    """The JWT-minting helper, for tests that need rejection-path variants."""
    return _mint_token


@pytest.fixture
def server_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Set the two required secrets in the environment for one test."""
    monkeypatch.setenv("BILTIQ_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("BILTIQ_HMAC_KEY", TEST_HMAC_KEY)
    yield


@pytest.fixture
def valid_token() -> str:
    """A valid, short-lived HS256 token signed with the test secret."""
    return _mint_token()
