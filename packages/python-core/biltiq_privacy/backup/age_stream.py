# SPDX-License-Identifier: MIT
"""age system-binary wrapper via subprocess.Popen streaming.

Two context-manager generators wrap the FiloSottile/age binary (>= 1.2.0) for
encrypted backup pipelines. Plaintext flows through pipes only; the wrapper
never holds plaintext on disk.

Usage:

    from biltiq_privacy.backup import open_age_writer, open_age_reader

    with open_age_writer(out_path, recipient="age1...") as plaintext_in:
        plaintext_in.write(b"...")

    with open_age_reader(in_path, identity_path=key_path) as plaintext_out:
        data = plaintext_out.read()

DO NOT introduce intermediate plaintext files on disk. The AC2/AC3 invariant
("plaintext never lands on disk between source and the age subprocess") is
enforced statically by tests/backup/test_no_intermediate_files.py — that test
greps this source for forbidden patterns and fails the build if any reappear.

Exception hierarchy:

- AgeNotInstalledError subclasses FileNotFoundError: callers can except either.
- AgeProcessError subclasses subprocess.CalledProcessError: callers can except
  either; the captured age stderr is on the .stderr attribute as bytes.

State: stateless / IO-only. No module-global cache, no env reads, no recipient
resolution, no key persistence. Callers (the BILTIQ-005+ backup orchestrator)
own those concerns.

See docs/adr/0003-age-streaming-pattern.md for the rationale (four rejected
encryption-backend alternatives + two rejected exception-hierarchy alternatives).
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


class AgeNotInstalledError(FileNotFoundError):
    """Raised at __enter__ when the age binary is not found on $PATH.

    Subclasses FileNotFoundError so callers can except either:

        try:
            with open_age_writer(out, recipient=r) as f:
                f.write(data)
        except FileNotFoundError:
            ...  # operator needs to run scripts/install-age.sh
    """


class AgeProcessError(subprocess.CalledProcessError):
    """Raised at __exit__ when the age subprocess exits non-zero.

    Subclasses subprocess.CalledProcessError; the captured age stderr is
    available as bytes on the .stderr attribute.
    """


def _resolve_age_binary() -> str:
    """Locate the age binary on $PATH; raise AgeNotInstalledError if absent.

    Looked up dynamically so monkey-patched test contexts can override the
    resolver.
    """
    location = shutil.which("age")
    if location is None:
        raise AgeNotInstalledError(
            "age binary not found on $PATH; run scripts/install-age.sh"
        )
    return location


def _close_quietly(handle: IO[bytes] | None) -> None:
    """Close a pipe handle if open; swallow benign close-of-closed errors."""
    if handle is None or handle.closed:
        return
    try:
        handle.close()
    except (ValueError, OSError):
        pass


@contextmanager
def open_age_writer(out_path: Path, *, recipient: str) -> Iterator[IO[bytes]]:
    """Stream plaintext bytes into an age-encrypted file at ``out_path``.

    Yields ``proc.stdin`` to the caller. On normal exit: closes stdin (signals
    EOF to age), drains stderr, waits the subprocess, raises AgeProcessError
    if the subprocess exited non-zero. On any exception escaping the body
    (including KeyboardInterrupt and SystemExit): closes pipe handles, waits
    the subprocess, unlinks any partial ciphertext at ``out_path``, and
    re-raises. The finally clause always drains and closes stderr.

    Args:
        out_path: Destination ciphertext path. Created by the age subprocess
            via its ``-o`` flag; deleted by the wrapper on any error path.
        recipient: age recipient string (``age1...``) for the encryption.

    Raises:
        AgeNotInstalledError: If the age binary is not on ``$PATH``.
        AgeProcessError: If the age subprocess exits non-zero after the body
            completes normally. Carries the captured stderr as bytes.
    """
    age_binary = _resolve_age_binary()
    proc = subprocess.Popen(
        [age_binary, "-r", recipient, "-o", str(out_path)],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None  # subprocess.PIPE invariant
    assert proc.stderr is not None

    try:
        try:
            yield proc.stdin
        except BaseException:
            _close_quietly(proc.stdin)
            proc.wait()
            if out_path.exists():
                out_path.unlink()
            raise
        _close_quietly(proc.stdin)
        stderr_bytes = proc.stderr.read()
        returncode = proc.wait()
        if returncode != 0:
            if out_path.exists():
                out_path.unlink()
            raise AgeProcessError(returncode, proc.args, stderr=stderr_bytes)
    finally:
        _close_quietly(proc.stderr)


@contextmanager
def open_age_reader(
    in_path: Path,
    *,
    identity_path: Path,
) -> Iterator[IO[bytes]]:
    """Stream plaintext bytes out of an age-encrypted file at ``in_path``.

    Yields ``proc.stdout`` to the caller. On normal exit: drains stderr,
    waits the subprocess, raises AgeProcessError if the subprocess exited
    non-zero. On any exception escaping the body: closes pipe handles, waits
    the subprocess, re-raises. The finally clause always drains and closes
    stderr.

    Args:
        in_path: Source ciphertext path. Not touched by the wrapper on any
            exit path.
        identity_path: Path to the age identity file (private key) for
            decryption.

    Raises:
        AgeNotInstalledError: If the age binary is not on ``$PATH``.
        AgeProcessError: If the age subprocess exits non-zero after the body
            completes normally (invalid identity, corrupted ciphertext, etc).
            Carries the captured stderr as bytes.
    """
    age_binary = _resolve_age_binary()
    proc = subprocess.Popen(
        [age_binary, "-d", "-i", str(identity_path), str(in_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None  # subprocess.PIPE invariant
    assert proc.stderr is not None

    try:
        try:
            yield proc.stdout
        except BaseException:
            _close_quietly(proc.stdout)
            proc.wait()
            raise
        _close_quietly(proc.stdout)
        stderr_bytes = proc.stderr.read()
        returncode = proc.wait()
        if returncode != 0:
            raise AgeProcessError(returncode, proc.args, stderr=stderr_bytes)
    finally:
        _close_quietly(proc.stderr)
