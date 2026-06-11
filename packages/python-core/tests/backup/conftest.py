# SPDX-License-Identifier: MIT
"""Shared fixtures for the age-wrapper test suite.

Fixtures that require the age binary call ``pytest.skip()`` if it is not on
``$PATH``; consumers inherit the skip automatically via pytest's
fixture-skip propagation, so tests using these fixtures are cleanly skipped
on CI cells without age installed (BILTIQ-004 AC6).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def age_test_keypair(tmp_path: Path) -> tuple[Path, str]:
    """Generate an ephemeral age keypair for a single test.

    Runs ``age-keygen -o <id>`` to write the identity (private key) to a
    file under ``tmp_path``, then ``age-keygen -y <id>`` to extract the
    matching recipient string. The keypair is unique per test invocation
    and discarded with ``tmp_path``; never committed.

    Returns:
        (identity_path, recipient): the private-key path to pass as
        ``identity_path=`` to ``open_age_reader``, and the recipient
        string to pass as ``recipient=`` to ``open_age_writer``.

    Skips:
        If ``age`` or ``age-keygen`` is not on ``$PATH`` — keeps the suite
        green on CI cells without the binary installed.
    """
    if shutil.which("age") is None:
        pytest.skip("age binary not on $PATH")
    if shutil.which("age-keygen") is None:
        pytest.skip("age-keygen binary not on $PATH")

    identity_path = tmp_path / "id.key"
    subprocess.run(
        ["age-keygen", "-o", str(identity_path)],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["age-keygen", "-y", str(identity_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return identity_path, result.stdout.strip()
