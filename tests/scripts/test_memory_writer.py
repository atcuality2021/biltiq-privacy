"""Tests for ``scripts/_memory_writer.py`` — AC1, AC4, AC6(a)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from scripts._memory_writer import (
    PIPE_BUF,
    SCHEMA_VERSION,
    STREAM_RELATIVE_PATH,
    MemoryEventTooLargeError,
    write_event,
)


def _read_lines(tmp_repo: Path) -> list[str]:
    return (tmp_repo / STREAM_RELATIVE_PATH).read_text(encoding="utf-8").splitlines()


def test_write_event_appends_one_valid_json_line(tmp_repo: Path) -> None:
    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": ["a"], "doing": [], "blockers": []},
    )
    lines = _read_lines(tmp_repo)
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "standup_post"
    assert event["payload"]["date"] == "2026-05-18"


def test_write_event_concurrent_writers_no_interleave(tmp_repo: Path) -> None:
    """4 threads × 50 events → 200 valid lines, no garbled records.

    Defends the POSIX atomic-append guarantee: a single ``os.write()`` of a
    sub-PIPE_BUF payload against an ``O_APPEND`` fd cannot interleave with
    concurrent writers' bytes.
    """
    n_threads = 4
    n_events_per_thread = 50

    def worker(thread_id: int) -> None:
        for i in range(n_events_per_thread):
            write_event("decision_made", {"thread": thread_id, "i": i, "title": "x"})

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = _read_lines(tmp_repo)
    assert len(lines) == n_threads * n_events_per_thread

    seen: set[tuple[int, int]] = set()
    for line in lines:
        event = json.loads(line)
        assert event["event_type"] == "decision_made"
        seen.add((event["payload"]["thread"], event["payload"]["i"]))
    assert len(seen) == n_threads * n_events_per_thread


def test_write_event_required_fields_present(tmp_repo: Path) -> None:
    write_event(
        "blocker_logged",
        {"title": "foo", "task_id": "BILTIQ-X", "since": "2026-05-18"},
    )
    event = json.loads(_read_lines(tmp_repo)[0])
    assert event["schema_version"] == SCHEMA_VERSION
    assert event["event_type"] == "blocker_logged"
    assert isinstance(event["payload"], dict)
    assert "ts" in event
    assert event["ts"].endswith("+00:00")


def test_write_event_rejects_oversize_payload(tmp_repo: Path) -> None:
    oversize_payload = {"blob": "x" * (PIPE_BUF + 100)}
    with pytest.raises(MemoryEventTooLargeError) as excinfo:
        write_event("commit_metadata", oversize_payload)
    assert "PIPE_BUF" in str(excinfo.value) or str(PIPE_BUF) in str(excinfo.value)

    stream = tmp_repo / STREAM_RELATIVE_PATH
    if stream.exists():
        assert stream.read_text(encoding="utf-8") == ""


def test_write_event_rejects_empty_event_type(tmp_repo: Path) -> None:
    with pytest.raises(ValueError, match="event_type"):
        write_event("", {"x": 1})


def test_write_event_rejects_non_dict_payload(tmp_repo: Path) -> None:
    with pytest.raises(ValueError, match="payload"):
        write_event("standup_post", "not-a-dict")  # type: ignore[arg-type]  # deliberate: testing input validation


def test_write_event_unknown_type_accepted(tmp_repo: Path) -> None:
    """Writer is permissive on ``event_type``; curator-side filtering handles unknown types (AC4 forward-compat)."""
    write_event("future_thing", {"experimental": True})
    event = json.loads(_read_lines(tmp_repo)[0])
    assert event["event_type"] == "future_thing"


def test_write_event_uses_BILTIQ_REPO_ROOT(tmp_repo: Path) -> None:
    """``tmp_repo`` redirects via ``BILTIQ_REPO_ROOT``; assert no writes leak outside ``tmp_path``."""
    write_event(
        "reflect_note",
        {"task_id": "BILTIQ-003", "what_went_well": [], "what_broke": []},
    )
    expected = tmp_repo / STREAM_RELATIVE_PATH
    assert expected.exists()
    assert expected.read_text(encoding="utf-8").count("\n") == 1
