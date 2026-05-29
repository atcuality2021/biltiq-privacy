"""Tests for vendored ``scripts/_paths.py`` — BILTIQ-006 AC1.

Covers the three public functions called by the writer / reader / curator
spine modules (steps 3-5):

  * ``_resolve_repo_root`` — explicit-arg > ``CLAUDE_PROJECT_DIR`` > cwd
    precedence.
  * ``_repo_hash`` — sha1[:12] stable across calls.
  * ``_safe_write`` — atomic stage-and-rename via ``Path.replace`` (POSIX
    rename guarantee; ``MoveFileExW`` on Windows).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts._paths import _repo_hash, _resolve_repo_root, _safe_write


def test_resolve_repo_root_falls_back_to_cwd_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert _resolve_repo_root() == tmp_path.resolve()


def test_resolve_repo_root_respects_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert _resolve_repo_root() == tmp_path.resolve()


def test_resolve_repo_root_explicit_arg_overrides_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(decoy))
    assert _resolve_repo_root(tmp_path) == tmp_path.resolve()


def test_repo_hash_returns_12_char_hex_stable(tmp_path: Path) -> None:
    first = _repo_hash(tmp_path)
    second = _repo_hash(tmp_path)
    assert first == second
    assert len(first) == 12
    assert all(c in "0123456789abcdef" for c in first)


def test_safe_write_replaces_target_atomically(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("original\n", encoding="utf-8")
    _safe_write(target, "replaced\n")
    assert target.read_text(encoding="utf-8") == "replaced\n"
    # Staging file must be cleaned up on the success path.
    assert not (tmp_path / "out.txt.tmp").exists()
