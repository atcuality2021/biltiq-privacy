"""Tests for ``scripts/_memory_curator.py`` Step-2 surface (lock + I/O + CLI contract).

Coverage: AC2 (no-op when stream empty), AC3 (lock + structured stdout),
AC6(b)(c)(d). Projection-side tests live in ``test_memory_curator_projection.py``
(Step 3).
"""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts._memory_curator import (
    LOCK_RELATIVE_PATH,
    MEMORY_RELATIVE_PATH,
    _acquire_lock,
    run,
)
from scripts._memory_writer import write_event


def _lock(repo: Path) -> Path:
    return repo / LOCK_RELATIVE_PATH


def _memory(repo: Path) -> Path:
    return repo / MEMORY_RELATIVE_PATH


def test_curator_acquires_lock_and_releases_on_exit(tmp_repo: Path) -> None:
    """After ``run()`` exits, the lock is acquirable by another invocation."""
    assert run([]) == 0
    assert _lock(tmp_repo).exists()
    with _acquire_lock(_lock(tmp_repo)) as acquired:
        assert acquired is True


def test_curator_lock_contention_prints_skipped_sentinel(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Second concurrent invocation prints the skipped sentinel + exits 0 (AC3, AC6d)."""
    started = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with _acquire_lock(_lock(tmp_repo)) as acquired:
            assert acquired is True
            started.set()
            release.wait(timeout=5.0)

    t = threading.Thread(target=holder, daemon=True)
    t.start()
    started.wait(timeout=5.0)

    try:
        exit_code = run([])
    finally:
        release.set()
        t.join(timeout=5.0)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip()) == {"skipped": "another curator already running"}


def test_curator_lock_file_created_with_mode_0600(tmp_repo: Path) -> None:
    """Lock file mode must be 0600 (design § Security R3 / AC6c)."""
    assert run([]) == 0
    mode = stat.S_IMODE(_lock(tmp_repo).stat().st_mode)
    assert mode == 0o600, f"lock file mode is {oct(mode)}, expected 0o600"


def test_curator_atomic_write_uses_replace(
    tmp_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When MEMORY.md is rewritten, ``os.replace`` is called with a temp source.

    Step 2's projection is a stub that returns MEMORY.md unchanged, so the
    atomic-write branch is normally skipped. Force it by monkeypatching the
    projector to return a different string — then assert ``os.replace`` was
    invoked with a ``.tmp`` source path and the real ``MEMORY.md`` as dest.
    """
    import scripts._memory_curator as curator

    def fake_project(
        events: list[dict[str, Any]],
        memory_text: str,
    ) -> tuple[str, dict[str, Any]]:
        return (
            memory_text + "\n# touched by curator\n",
            {"events_seen": 0, "events_projected": 1, "sections_written": ["forced"]},
        )

    monkeypatch.setattr(curator, "_project_events", fake_project)

    replace_calls: list[tuple[str, str]] = []
    original_replace = os.replace

    def spy_replace(
        src: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        dst: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        replace_calls.append((str(src), str(dst)))
        original_replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

    monkeypatch.setattr(os, "replace", spy_replace)

    assert run([]) == 0
    assert len(replace_calls) == 1
    src, dst = replace_calls[0]
    assert src.endswith(".tmp"), f"expected temp source, got {src!r}"
    assert dst == str(_memory(tmp_repo))


def test_curator_empty_stream_no_op(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty stream → exit 0, MEMORY.md unchanged byte-for-byte (AC2)."""
    before = _memory(tmp_repo).read_bytes()
    assert run([]) == 0
    after = _memory(tmp_repo).read_bytes()
    assert before == after, "MEMORY.md must be byte-equal when stream is empty"

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip())
    assert stats["events_seen"] == 0
    assert stats["events_projected"] == 0
    assert stats["sections_written"] == []


def test_curator_emits_structured_stdout_on_success(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Success stdout is one JSON line with the three documented keys (AC3)."""
    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": [], "doing": [], "blockers": []},
    )
    write_event(
        "decision_made",
        {"title": "x", "rationale": "y", "adr_ref": None},
    )

    assert run([]) == 0

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip())
    assert stats["events_seen"] == 2
    assert "events_projected" in stats
    assert "sections_written" in stats
    assert isinstance(stats["sections_written"], list)
