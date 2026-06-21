# SPDX-License-Identifier: MIT
"""JWT verification — PyJWT, HS256, verify-only (BILTIQ-013, ADR-0007).

This is the **only** module that imports ``jwt`` in production code. The server
verifies tokens; it never issues them (token minting is the consumer's concern).
The algorithm is pinned to a single-element allow-list, which closes the
algorithm-confusion class of attack: a token presenting ``alg: none`` or any
algorithm other than ``HS256`` (including another HMAC variant such as
``HS512``) is rejected outright before any claim is trusted.
"""
from __future__ import annotations

import jwt
from fastapi import HTTPException, status

#: Single-element allow-list. Widening this re-opens the alg-confusion class —
#: do not change without revisiting ADR-0007.
_ALGORITHMS = ["HS256"]

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def verify_token(token: str, *, secret: str) -> dict[str, object]:
    """Verify an HS256 JWT's signature and expiry, returning its claims.

    Args:
        token: the raw bearer token, without the ``Bearer `` prefix.
        secret: the shared HS256 secret (sourced from ``BILTIQ_JWT_SECRET``).

    Returns:
        The decoded claim set.

    Raises:
        HTTPException: ``401`` on any expired, malformed, wrong-secret, or
            disallowed-algorithm token. The detail is generic and never echoes
            the token or the secret.
    """
    try:
        # ExpiredSignatureError is a subclass of InvalidTokenError, so it must
        # be handled first to give the caller a precise "expired" signal.
        claims: dict[str, object] = jwt.decode(
            token,
            secret,
            algorithms=_ALGORITHMS,
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc
    return claims
