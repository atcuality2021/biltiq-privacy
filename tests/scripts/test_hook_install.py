"""Tests for ``scripts/install-curator-hook.sh`` and ``scripts/hooks/post-commit.sh`` — Step 5.

Coverage: AC8 (opt-in installer + background hook + log-content discipline),
AC9 (idempotency + uninstall + failure swallowing). Design § Security clauses
on symlink-clobber refusal and payload-free hook logging.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HOOK_DEST_REL = ".git/hooks/post-commit"
HOOK_SOURCE_REL = "scripts/hooks/post-commit.sh"
INSTALLER_REL = "scripts/install-curator-hook.sh"
HOOK_LOG_REL = ".biltiq/curator-hook.log"


def _run_installer(
    repo: Path,
    *args: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_extra is not None:
        env.update(env_extra)
    return subprocess.run(
        ["sh", str(repo / INSTALLER_REL), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def _run_hook(
    repo: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_extra is not None:
        env.update(env_extra)
    return subprocess.run(
        ["sh", str(repo / HOOK_SOURCE_REL)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def _wait_for_log_contains(log_path: Path, needle: str, timeout: float = 3.0) -> bool:
    """Poll ``log_path`` until it contains ``needle`` or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if log_path.exists() and needle in log_path.read_text(encoding="utf-8"):
            return True
        time.sleep(0.05)
    return False


def test_installer_creates_symlink(git_tmp_repo: Path) -> None:
    """First install creates a symlink pointing at the hook source (AC8)."""
    result = _run_installer(git_tmp_repo)
    assert result.returncode == 0, f"installer exit {result.returncode}; stderr={result.stderr!r}"

    dest = git_tmp_repo / HOOK_DEST_REL
    assert dest.is_symlink(), f"{dest} is not a symlink"

    target = os.readlink(dest)
    expected = str(git_tmp_repo / HOOK_SOURCE_REL)
    assert target == expected, f"symlink target {target!r} != expected {expected!r}"


def test_installer_idempotent(git_tmp_repo: Path) -> None:
    """Running the installer twice yields exactly one symlink (AC9)."""
    first = _run_installer(git_tmp_repo)
    assert first.returncode == 0

    second = _run_installer(git_tmp_repo)
    assert second.returncode == 0
    assert "already installed" in second.stdout.lower()

    hooks = list((git_tmp_repo / ".git" / "hooks").glob("post-commit*"))
    assert len(hooks) == 1, f"expected exactly one post-commit hook, got {hooks}"
    assert hooks[0].is_symlink()


def test_installer_uninstall_removes_symlink(git_tmp_repo: Path) -> None:
    """``--uninstall`` removes the symlink and returns 0 (AC9)."""
    assert _run_installer(git_tmp_repo).returncode == 0

    uninstall = _run_installer(git_tmp_repo, "--uninstall")
    assert uninstall.returncode == 0, f"uninstall stderr={uninstall.stderr!r}"
    assert not (git_tmp_repo / HOOK_DEST_REL).exists()


def test_installer_refuses_to_clobber_non_symlink_without_force(git_tmp_repo: Path) -> None:
    """Pre-existing regular file at post-commit is preserved unless ``--force`` (AC8, Security)."""
    dest = git_tmp_repo / HOOK_DEST_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    sentinel = "#!/bin/sh\necho 'sentinel hook from another plugin'\nexit 0\n"
    dest.write_text(sentinel, encoding="utf-8")

    refusal = _run_installer(git_tmp_repo)
    assert refusal.returncode != 0, "installer must refuse to clobber non-symlink"
    assert dest.read_text(encoding="utf-8") == sentinel, "sentinel hook content was modified"
    assert not dest.is_symlink()

    forced = _run_installer(git_tmp_repo, "--force")
    assert forced.returncode == 0, f"--force stderr={forced.stderr!r}"
    assert dest.is_symlink(), "expected symlink after --force"


def test_hook_swallows_curator_failure(git_tmp_repo: Path) -> None:
    """Curator failure does not abort the commit; failure recorded in the hook log (AC8, AC9, Risk R3)."""
    fake_bin = git_tmp_repo / "_fake_bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "#!/bin/sh\necho 'FAKE-PYTHON-FAIL' >&2\nexit 1\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env_extra = {"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"}
    result = _run_hook(git_tmp_repo, env_extra=env_extra)
    assert result.returncode == 0, (
        f"hook must exit 0 even on curator failure; got {result.returncode}, stderr={result.stderr!r}"
    )

    log_path = git_tmp_repo / HOOK_LOG_REL
    assert _wait_for_log_contains(log_path, "FAKE-PYTHON-FAIL"), (
        f"fake-python stderr not in {log_path}; "
        f"contents: {log_path.read_text(encoding='utf-8') if log_path.exists() else '<missing>'!r}"
    )


def test_hook_does_not_log_payload_contents(git_tmp_repo: Path) -> None:
    """Hook log records curator JSON only; payload contents never leak in (AC8, AP#5)."""
    canary = "CANARY-XYZ-12345-67890"
    writer_call = (
        "import os, sys;"
        f"sys.path.insert(0, {str(git_tmp_repo)!r});"
        f"os.environ['BILTIQ_REPO_ROOT'] = {str(git_tmp_repo)!r};"
        "from scripts._memory_writer import write_event;"
        f"write_event('decision_made', {{'title': 'x', 'rationale': {canary!r}, 'adr_ref': None}})"
    )
    subprocess.run(
        [sys.executable, "-c", writer_call],
        check=True,
        capture_output=True,
    )

    result = _run_hook(git_tmp_repo)
    assert result.returncode == 0

    log_path = git_tmp_repo / HOOK_LOG_REL
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if log_path.exists() and log_path.stat().st_size > 0:
            break
        time.sleep(0.05)

    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert canary not in log_text, f"payload canary leaked into hook log: {log_text!r}"


def test_hook_runs_curator_in_background(git_tmp_repo: Path) -> None:
    """Hook returns quickly even when curator is synthetically slow — proves background spawn (AC8)."""
    sleep_seconds = 2.0
    curator_path = git_tmp_repo / "scripts" / "_memory_curator.py"
    curator_path.write_text(
        f"#!/usr/bin/env python3\nimport time, sys\ntime.sleep({sleep_seconds})\nsys.exit(0)\n",
        encoding="utf-8",
    )

    start = time.perf_counter()
    result = _run_hook(git_tmp_repo)
    elapsed = time.perf_counter() - start

    assert result.returncode == 0
    assert elapsed < 1.0, (
        f"hook took {elapsed:.3f}s — curator is not running in the background "
        f"(sleep was {sleep_seconds}s)"
    )

    time.sleep(sleep_seconds + 0.3)
