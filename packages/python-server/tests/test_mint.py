# SPDX-License-Identifier: MIT
"""Behavioural tests for the operator token-mint CLI (BILTIQ-013a).

Covers AC1 (verifiable token, stdout-only), AC2 (no --secret flag), AC3
(fail-fast on missing secret), AC4 (sub/ttl, tz-aware, non-positive reject),
AC5 (extensible --claim with malformed/reserved rejection), plus the algorithm
drift pin against the verify side. ``auth`` is imported only by the test (the
runtime mint module never imports it) to assert the minted token round-trips and
the algorithm matches.
"""
from __future__ import annotations

from datetime import datetime

import jwt
import pytest
from fastapi import HTTPException

from biltiq_privacy_server import auth, mint

_SECRET = "operator-mint-test-secret-not-real-0123456789"


# --- AC1: mints a verifiable token, stdout = token only ----------------------


def test_mints_token_verifiable_by_verify_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    rc = mint.main(["--sub", "ops"])
    captured = capsys.readouterr()
    assert rc == 0
    token = captured.out.rstrip("\n")
    # stdout is exactly the token + one trailing newline, nothing else; stderr empty.
    assert captured.out == token + "\n"
    assert captured.err == ""
    claims = auth.verify_token(token, secret=_SECRET)
    assert claims["sub"] == "ops"


def test_token_does_not_verify_under_wrong_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    assert mint.main(["--sub", "ops"]) == 0
    token = capsys.readouterr().out.rstrip("\n")
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_token(token, secret="a-different-secret-entirely-9876543210")
    assert excinfo.value.status_code == 401


# --- AC2: secret is env-only, no --secret flag -------------------------------


def test_parser_has_no_secret_flag() -> None:
    parser = mint.build_parser()
    options = {opt for action in parser._actions for opt in action.option_strings}
    assert "--secret" not in options
    assert "--key" not in options
    # The flags that DO exist are the safe ones.
    assert "--sub" in options
    assert "--ttl" in options
    assert "--claim" in options


# --- AC3: fail-fast on missing/empty secret ----------------------------------


@pytest.mark.parametrize("unset", [True, False])
def test_missing_or_empty_secret_fails_fast(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], unset: bool
) -> None:
    if unset:
        monkeypatch.delenv("BILTIQ_JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("BILTIQ_JWT_SECRET", "")
    rc = mint.main(["--sub", "ops"])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""  # nothing minted
    assert "BILTIQ_JWT_SECRET" in captured.err  # names the var…
    assert "=" not in captured.err.split("BILTIQ_JWT_SECRET", 1)[1]  # …never echoes a value


# --- AC4: sub + ttl, tz-aware iat/exp ----------------------------------------


def test_build_payload_is_tz_aware_and_honours_ttl() -> None:
    payload = mint._build_payload(subject="x", ttl_seconds=60, extra_claims={})
    iat, exp = payload["iat"], payload["exp"]
    assert isinstance(iat, datetime) and iat.tzinfo is not None
    assert isinstance(exp, datetime) and exp.tzinfo is not None
    assert (exp - iat).total_seconds() == 60
    assert payload["sub"] == "x"


def test_default_ttl_is_3600(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    assert mint.main(["--sub", "ops"]) == 0
    claims = jwt.decode(capsys.readouterr().out.rstrip("\n"), _SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 3600


def test_explicit_ttl_sets_exp(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    assert mint.main(["--sub", "ops", "--ttl", "1800"]) == 0
    claims = jwt.decode(capsys.readouterr().out.rstrip("\n"), _SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 1800


@pytest.mark.parametrize("bad", ["0", "-5", "notanint"])
def test_invalid_ttl_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], bad: str
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    with pytest.raises(SystemExit) as excinfo:
        mint.main(["--sub", "ops", "--ttl", bad])
    assert excinfo.value.code == 2
    assert "--ttl" in capsys.readouterr().err


def test_missing_sub_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        mint.main([])
    assert excinfo.value.code == 2
    assert "--sub" in capsys.readouterr().err


# --- AC5: extensible --claim k=v ---------------------------------------------


def test_extra_claims_merged_as_strings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    rc = mint.main(["--sub", "ops", "--claim", "role=admin", "--claim", "team=privacy"])
    assert rc == 0
    claims = jwt.decode(capsys.readouterr().out.rstrip("\n"), _SECRET, algorithms=["HS256"])
    assert claims["role"] == "admin"
    assert claims["team"] == "privacy"


def test_claim_value_may_contain_equals(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    assert mint.main(["--sub", "ops", "--claim", "kv=a=b"]) == 0
    claims = jwt.decode(capsys.readouterr().out.rstrip("\n"), _SECRET, algorithms=["HS256"])
    assert claims["kv"] == "a=b"  # split on the FIRST '=' only


@pytest.mark.parametrize("bad", ["noequals", "=novalue"])
def test_malformed_claim_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], bad: str
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    rc = mint.main(["--sub", "ops", "--claim", bad])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "malformed --claim" in captured.err


@pytest.mark.parametrize("reserved", ["sub=x", "iat=1", "exp=1"])
def test_reserved_claim_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], reserved: str
) -> None:
    monkeypatch.setenv("BILTIQ_JWT_SECRET", _SECRET)
    rc = mint.main(["--sub", "ops", "--claim", reserved])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "reserved claim" in captured.err


# --- Algorithm drift pin (design § Algorithm constant) -----------------------


def test_mint_algorithm_matches_verify_side() -> None:
    assert mint._MINT_ALGORITHM == auth._ALGORITHMS[0]
    assert len(auth._ALGORITHMS) == 1  # verify side stays single-element (no alg-confusion)
