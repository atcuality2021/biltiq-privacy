# SPDX-License-Identifier: MIT
"""Tests for biltiq_privacy.backup.age_stream — the age system-binary wrapper.

Step 2 lands AC1 (AgeNotInstalledError gate). Step 3 adds AC2/AC3/AC5
(round-trip). Step 4 adds AC4 (AgeProcessError on invalid recipient and
on corrupted ciphertext). The AC10 static-grep meta-test lives in
test_no_intermediate_files.py.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from biltiq_privacy.backup import (
    AgeNotInstalledError,
    AgeProcessError,
    open_age_reader,
    open_age_writer,
)

_skip_if_no_age = pytest.mark.skipif(
    shutil.which("age") is None,
    reason="age binary not on $PATH",
)


def test_age_not_installed_raises_at_enter_for_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: writer raises AgeNotInstalledError when age binary is absent.

    Subclass contract: the exception is also a FileNotFoundError so library
    callers can except either without importing AgeNotInstalledError.
    """
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(AgeNotInstalledError) as exc_info:
        with open_age_writer(tmp_path / "out.age", recipient="age1fake"):
            pytest.fail("body must not run when age binary is missing")

    assert isinstance(exc_info.value, FileNotFoundError)


def test_age_not_installed_raises_at_enter_for_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: reader raises AgeNotInstalledError when age binary is absent."""
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(AgeNotInstalledError) as exc_info:
        with open_age_reader(
            tmp_path / "in.age",
            identity_path=tmp_path / "id.key",
        ):
            pytest.fail("body must not run when age binary is missing")

    assert isinstance(exc_info.value, FileNotFoundError)


@_skip_if_no_age
def test_age_present_or_skip_works() -> None:
    """AC6: positive control — if this test runs, the skipif wiring is intact.

    The module-level ``_skip_if_no_age`` marker skips this test when the age
    binary is absent. So either: (a) age is present and ``shutil.which("age")``
    returns a non-None path — the assertion passes by construction; or
    (b) age is absent and pytest reports SKIPPED — also a healthy outcome.

    The failure mode this guards against is the test suite silently turning
    into a no-op because the skipif marker breaks (wrong binary name, wrong
    condition, etc.); then this test would fail loudly on cells that lack
    age instead of being cleanly skipped.
    """
    assert shutil.which("age") is not None


def test_round_trip_synthetic_plaintext(
    age_test_keypair: tuple[Path, str],
    tmp_path: Path,
) -> None:
    """AC2 + AC3 + AC5: write plaintext through the wrapper, read it back, verify byte-equal.

    1024 bytes of synthetic plaintext (``b"\\x42" * 1024``) — no real PII.
    The keypair is ephemeral (lives in ``tmp_path``) and never committed.
    Plaintext is only ever resident in the writer's stdin pipe and the
    reader's stdout pipe; the wrapper guarantees no plaintext lands on disk
    (AC2/AC3 invariant, statically enforced by test_no_intermediate_files.py
    in Step 6).
    """
    identity_path, recipient = age_test_keypair
    ciphertext_path = tmp_path / "ciphertext.age"
    plaintext_in = b"\x42" * 1024

    with open_age_writer(ciphertext_path, recipient=recipient) as sink:
        sink.write(plaintext_in)

    assert ciphertext_path.stat().st_size > 0

    with open_age_reader(ciphertext_path, identity_path=identity_path) as source:
        plaintext_out = source.read()

    assert plaintext_in == plaintext_out


@_skip_if_no_age
def test_invalid_recipient_raises_age_process_error(tmp_path: Path) -> None:
    """AC4: invalid recipient string causes age to exit non-zero; wrapper raises AgeProcessError.

    Subclass contract: the exception is also a subprocess.CalledProcessError;
    age's stderr is captured as bytes on `exc.stderr`.
    """
    out_path = tmp_path / "out.age"

    with pytest.raises(AgeProcessError) as exc_info:
        with open_age_writer(out_path, recipient="not-a-real-recipient") as sink:
            sink.write(b"any plaintext")

    exc = exc_info.value
    assert isinstance(exc, subprocess.CalledProcessError)
    assert isinstance(exc.stderr, bytes)
    assert b"error" in exc.stderr.lower()
    assert not out_path.exists(), "partial ciphertext must be unlinked on failure"


@_skip_if_no_age
def test_corrupted_ciphertext_raises_age_process_error(
    age_test_keypair: tuple[Path, str],
    tmp_path: Path,
) -> None:
    """AC4: a single byte flip in the ciphertext causes decrypt to raise AgeProcessError.

    Writes a fresh ciphertext, flips byte 256 (past the age v1 header for
    single-recipient files, safely inside the encrypted payload), then
    reads via open_age_reader. age's Poly1305 MAC rejects the tamper and
    exits non-zero.
    """
    identity_path, recipient = age_test_keypair
    ciphertext_path = tmp_path / "ciphertext.age"

    with open_age_writer(ciphertext_path, recipient=recipient) as sink:
        sink.write(b"\x42" * 1024)

    raw = bytearray(ciphertext_path.read_bytes())
    assert len(raw) > 256, "round-trip ciphertext shorter than expected"
    raw[256] ^= 0xFF
    ciphertext_path.write_bytes(bytes(raw))

    with pytest.raises(AgeProcessError) as exc_info:
        with open_age_reader(ciphertext_path, identity_path=identity_path) as source:
            source.read()

    exc = exc_info.value
    assert isinstance(exc, subprocess.CalledProcessError)
    assert isinstance(exc.stderr, bytes)
    assert len(exc.stderr) > 0
