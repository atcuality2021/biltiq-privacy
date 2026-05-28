# SPDX-License-Identifier: MIT
"""AC10 static-grep meta-test for biltiq_privacy.backup.age_stream.

Enforces the AC2/AC3 invariant — "plaintext never lands on disk between
the caller and the age subprocess" — at CI time by scanning the wrapper
source for patterns that would route plaintext through the filesystem.
Code review alone is fallible; this test makes the gate mechanical.

Runs unconditionally (no age binary required), so it stays green on CI
cells without the binary and turns red the moment a forbidden pattern
is introduced.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_AGE_STREAM_SOURCE_PATH = (
    Path(__file__).parent.parent.parent / "biltiq_privacy" / "backup" / "age_stream.py"
)


_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    "NamedTemporaryFile",
    "tempfile.mkstemp",
    "tempfile.NamedTemporary",
    "Path.write_bytes",
    ".write_text(",
)


@pytest.mark.parametrize("pattern", _FORBIDDEN_PATTERNS)
def test_age_stream_source_has_no_intermediate_files(pattern: str) -> None:
    """AC10: age_stream.py source must not contain the named pattern.

    Each pattern would let plaintext touch the filesystem between the
    caller and the age subprocess, breaking the AC2/AC3 invariant. If a
    legitimate need arises, the wrapper API must change first; revisit
    ADR-0003 before suppressing this test.
    """
    assert _AGE_STREAM_SOURCE_PATH.is_file(), (
        f"age_stream.py source not found at {_AGE_STREAM_SOURCE_PATH}; "
        "did the module move? Update _AGE_STREAM_SOURCE_PATH."
    )
    source = _AGE_STREAM_SOURCE_PATH.read_text(encoding="utf-8")
    assert pattern not in source, (
        f"Forbidden pattern {pattern!r} appears in age_stream.py — this "
        "breaks the AC2/AC3 invariant (plaintext must never land on disk "
        "between the caller and the age subprocess). See ADR-0003."
    )
