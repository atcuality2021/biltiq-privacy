# SPDX-License-Identifier: MIT
"""Operator token-mint CLI for biltiq-privacy-server (BILTIQ-013a).

``biltiq-privacy-mint`` signs a short-lived HS256 JWT that the verify-only server
(BILTIQ-013, ADR-0007) accepts. It is a **standalone operator helper, not part of
the running server**: this module is the single production caller of
``jwt.encode``, and nothing in the ``biltiq_privacy_server.app:app`` ASGI import
graph imports it — so the server's verify-only guarantee is preserved (asserted by
``tests/test_mint_invariant.py``). To keep this CLI's import graph small
(``argparse`` + ``pyjwt`` + ``config``), the module does **not** import ``auth``
(which pulls in FastAPI); the HS256 constant is kept module-local and pinned to the
verify side by an equality test in ``tests/test_mint.py``.

The signing secret is read **only** from the ``BILTIQ_JWT_SECRET`` environment
variable — the same var the server verifies against — never from a CLI argument,
so a signing key never lands in ``argv`` / ``ps`` / shell history. The minted token
is the *only* thing written to stdout (pipe-friendly:
``TOKEN=$(biltiq-privacy-mint --sub ops)``); every diagnostic goes to stderr.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt

from biltiq_privacy_server.config import _JWT_SECRET_ENV

#: HS256 — must equal ``auth._ALGORITHMS[0]`` (the verify side). Kept module-local
#: so this CLI's import graph stays ``argparse`` + ``pyjwt`` + ``config`` (importing
#: ``auth`` would pull in FastAPI); drift from the verify side is pinned by
#: ``tests/test_mint.py::test_mint_algorithm_matches_verify_side``.
_MINT_ALGORITHM = "HS256"

#: Default token lifetime in seconds.
_DEFAULT_TTL_SECONDS = 3600

#: Claims the mint controls itself; an operator cannot override them via ``--claim``
#: (``sub`` comes from ``--sub``; ``iat``/``exp`` are derived from the clock + ``--ttl``).
_RESERVED_CLAIMS = frozenset({"sub", "iat", "exp"})


class MintError(Exception):
    """A user-facing minting failure.

    :func:`main` converts it into a stderr message + non-zero exit. Distinct from
    argparse's own usage errors (which argparse renders and raises as
    ``SystemExit``).
    """


def _positive_int(raw: str) -> int:
    """argparse ``type=`` for ``--ttl``: a strictly positive integer (seconds)."""
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--ttl must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"--ttl must be > 0, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the ``biltiq-privacy-mint`` argument parser.

    Deliberately exposes **no** secret-bearing flag — the signing secret is read
    from the environment only (asserted by
    ``tests/test_mint.py::test_parser_has_no_secret_flag``).
    """
    parser = argparse.ArgumentParser(
        prog="biltiq-privacy-mint",
        description=(
            "Mint a short-lived HS256 bearer token for biltiq-privacy-server. "
            "Reads the signing secret from the BILTIQ_JWT_SECRET environment "
            "variable; the secret is never a command-line argument."
        ),
    )
    parser.add_argument("--sub", required=True, help="Token subject (the 'sub' claim).")
    parser.add_argument(
        "--ttl",
        type=_positive_int,
        default=_DEFAULT_TTL_SECONDS,
        help="Token lifetime in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--claim",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra string claim, repeatable. Cannot set sub/iat/exp.",
    )
    return parser


def _parse_claims(raw_claims: Sequence[str]) -> dict[str, str]:
    """Parse repeatable ``--claim KEY=VALUE`` pairs into a dict of string claims.

    Raises:
        MintError: a pair without ``=``, an empty key, or a reserved claim name
            (``sub``/``iat``/``exp``).
    """
    claims: dict[str, str] = {}
    for item in raw_claims:
        key, sep, value = item.partition("=")
        if not sep:
            raise MintError(f"malformed --claim {item!r}: expected KEY=VALUE")
        if not key:
            raise MintError(f"malformed --claim {item!r}: empty key")
        if key in _RESERVED_CLAIMS:
            raise MintError(
                f"reserved claim {key!r} cannot be set via --claim "
                "(sub is set by --sub; iat/exp are derived from --ttl)"
            )
        claims[key] = value
    return claims


def _read_secret() -> str:
    """Read the HS256 signing secret from ``BILTIQ_JWT_SECRET`` (env-only).

    Raises:
        MintError: the env var is unset or empty. The message names the var but
            never echoes any value.
    """
    secret = os.environ.get(_JWT_SECRET_ENV)
    if not secret:
        raise MintError(f"{_JWT_SECRET_ENV} is required but is unset or empty.")
    return secret


def _build_payload(
    *, subject: str, ttl_seconds: int, extra_claims: dict[str, str]
) -> dict[str, object]:
    """Build the claim set ``{sub, iat, exp}`` + extra claims, tz-aware UTC.

    Shape matches ``tests/conftest.py::_mint_token`` so minted tokens verify
    against ``auth.verify_token`` unchanged.
    """
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    payload.update(extra_claims)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point. Print the token to stdout; return the exit code.

    stdout receives exactly the token + a trailing newline and nothing else; all
    errors go to stderr with a non-zero return and no secret value is ever printed.
    Argparse usage errors (missing ``--sub``, non-positive ``--ttl``) are rendered
    by argparse to stderr and raised as ``SystemExit(2)``.
    """
    args = build_parser().parse_args(argv)
    try:
        secret = _read_secret()
        extra_claims = _parse_claims(args.claim)
        payload = _build_payload(
            subject=args.sub, ttl_seconds=args.ttl, extra_claims=extra_claims
        )
        token = jwt.encode(payload, secret, algorithm=_MINT_ALGORITHM)
    except MintError as exc:
        sys.stderr.write(f"biltiq-privacy-mint: error: {exc}\n")
        return 2
    sys.stdout.write(token + "\n")
    return 0
