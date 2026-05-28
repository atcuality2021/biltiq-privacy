# SPDX-License-Identifier: MIT
"""Tests for biltiq_privacy.backup.age_stream — the age system-binary wrapper.

Step 2 lands AC1 (AgeNotInstalledError gate). Subsequent BILTIQ-004 Build
steps extend this file with the round-trip, error-path, and positive-control
tests; the AC10 static-grep meta-test lives in test_no_intermediate_files.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from biltiq_privacy.backup import (
    AgeNotInstalledError,
    open_age_reader,
    open_age_writer,
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
