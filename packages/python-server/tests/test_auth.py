# SPDX-License-Identifier: MIT
"""JWT verification tests (BILTIQ-013, AC5, ADR-0007).

Covers the success path plus every rejection path, including the
algorithm-confusion guard: tokens presenting ``alg: none`` or an HMAC variant
other than HS256 must be rejected by the single-element allow-list.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import HTTPException, status

from biltiq_privacy_server.auth import verify_token


def test_verify_token_valid_returns_claims(
    token_minter: Callable[..., str], jwt_secret: str
) -> None:
    """A well-formed token signed with the secret decodes to its claims (AC5)."""
    token = token_minter(subject="alice")
    claims = verify_token(token, secret=jwt_secret)
    assert claims["sub"] == "alice"


def test_verify_token_expired_raises_401(
    token_minter: Callable[..., str], jwt_secret: str
) -> None:
    """An expired token → 401 (AC5)."""
    token = token_minter(expires_in=timedelta(minutes=-1))
    with pytest.raises(HTTPException) as exc_info:
        verify_token(token, secret=jwt_secret)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in str(exc_info.value.detail).lower()


def test_verify_token_wrong_secret_raises_401(
    token_minter: Callable[..., str], jwt_secret: str
) -> None:
    """A signature minted with a different secret → 401 (AC5)."""
    token = token_minter(secret="a-different-secret-padded-to-32+bytes!!")
    with pytest.raises(HTTPException) as exc_info:
        verify_token(token, secret=jwt_secret)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_verify_token_malformed_raises_401(jwt_secret: str) -> None:
    """A non-JWT string → 401, not an unhandled crash (AC5)."""
    with pytest.raises(HTTPException) as exc_info:
        verify_token("not-a-jwt", secret=jwt_secret)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# The HS512 case mints with a short key purely to build a rejected token; PyJWT's
# key-length advisory is expected noise on that path, not a finding under test.
@pytest.mark.filterwarnings("ignore:The HMAC key")
@pytest.mark.parametrize("algorithm", ["none", "HS512"])
def test_verify_token_rejects_disallowed_algorithms(
    algorithm: str, token_minter: Callable[..., str], jwt_secret: str
) -> None:
    """alg:none and a mismatched HMAC variant are both rejected (AC5, alg-confusion).

    ``none`` is the canonical unsigned-token attack; ``HS512`` proves the
    allow-list pins HS256 *exactly* rather than accepting any HMAC family.
    """
    # alg:none requires an empty key; HS512 reuses the real secret to show the
    # rejection is about the algorithm, not the signature.
    secret = "" if algorithm == "none" else jwt_secret
    token = token_minter(secret=secret, algorithm=algorithm)
    with pytest.raises(HTTPException) as exc_info:
        verify_token(token, secret=jwt_secret)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
