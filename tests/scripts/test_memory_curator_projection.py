"""Tests for ``scripts/_memory_curator.py`` projection logic — Step 3.

Coverage: AC2 (projection per event type + multi-event ordering),
AC3 (manual-section survival + fail-closed marker handling), AC4 (forward-
compat unknown types + schema versions), AC6(b)(e).

BILTIQ-006 Step 3 sideline (transient): this file is file-level skipped
between Steps 3 and 5 of the BILTIQ-006 vendoring cascade. The import of
``STREAM_RELATIVE_PATH`` from ``scripts._memory_writer`` would otherwise
fail at collection time — v1.10.1 ``_memory_writer.py`` does not export
that constant (the stream path is inlined as a literal in v1.10.1). The
try/except below resolves the import to ``None`` so the module loads; the
``pytestmark.skip`` then prevents any of the tests from running. Step 5
vendors ``_memory_curator.py`` to v1.10.1 and replaces this file (via
DELETE) with a port of the plugin's ``tests/spine/test_curator.py``. The
skip is removed by the DELETE. See ``docs/specs/BILTIQ-006/plan.html``
§ Step 5 file-list + revision-5 change-history row for the full rationale.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "awaits BILTIQ-006 step 5 curator swap "
        "(this file is DELETEd at step 5; see plan.html § Step 5 + revision-5)"
    )
)

from scripts._memory_curator import MEMORY_RELATIVE_PATH, run

try:
    from scripts._memory_writer import STREAM_RELATIVE_PATH, write_event
except ImportError:
    # v1.10.1 ``_memory_writer.py`` removed ``STREAM_RELATIVE_PATH`` (the
    # stream path is now an inlined literal). The file-level pytestmark.skip
    # above prevents any test from referencing these names; the fallbacks
    # keep collection clean for the Step 3 → Step 5 transition window.
    STREAM_RELATIVE_PATH = ""  # type: ignore[assignment]
    write_event = None  # type: ignore[assignment]


def _memory(repo: Path) -> Path:
    return repo / MEMORY_RELATIVE_PATH


def _extract_auto_block(memory_text: str, name: str) -> str:
    start_marker = f"<!-- auto:{name}:start -->"
    end_marker = f"<!-- auto:{name}:end -->"
    start = memory_text.find(start_marker)
    end = memory_text.find(end_marker)
    if start == -1 or end == -1:
        raise AssertionError(f"auto:{name} markers not found")
    return memory_text[start + len(start_marker):end]


def _extract_manual_block(memory_text: str) -> str:
    start = memory_text.find("<!-- manual:start -->")
    end = memory_text.find("<!-- manual:end -->")
    if start == -1 or end == -1:
        raise AssertionError("manual markers not found")
    return memory_text[start + len("<!-- manual:start -->"):end]


def test_projects_standup_post_into_current_focus(tmp_repo: Path) -> None:
    """One standup_post → expected text in auto:current_focus block (AC2)."""
    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": ["x"], "doing": ["BILTIQ-003 Step 3"], "blockers": []},
    )
    assert run([]) == 0

    current_focus = _extract_auto_block(
        _memory(tmp_repo).read_text(encoding="utf-8"), "current_focus"
    )
    assert "2026-05-18" in current_focus
    assert "BILTIQ-003 Step 3" in current_focus


def test_projects_commit_metadata_into_code_areas(tmp_repo: Path) -> None:
    """commit_metadata event → files_touched listed in auto:code_areas block (AC2)."""
    write_event(
        "commit_metadata",
        {
            "sha": "abc1234",
            "task_id": "BILTIQ-003",
            "files_touched": [
                "scripts/_memory_curator.py",
                "tests/scripts/test_memory_curator_projection.py",
            ],
        },
    )
    assert run([]) == 0

    code_areas = _extract_auto_block(
        _memory(tmp_repo).read_text(encoding="utf-8"), "code_areas"
    )
    assert "scripts/_memory_curator.py" in code_areas
    assert "tests/scripts/test_memory_curator_projection.py" in code_areas


def test_projects_blocker_logged_alongside_standup(tmp_repo: Path) -> None:
    """Multi-event projection: standup_post + blocker_logged both in current_focus (AC2)."""
    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": [], "doing": ["x"], "blockers": []},
    )
    write_event(
        "blocker_logged",
        {"title": "presidio pin", "task_id": "BILTIQ-002", "since": "2026-05-17"},
    )
    assert run([]) == 0

    current_focus = _extract_auto_block(
        _memory(tmp_repo).read_text(encoding="utf-8"), "current_focus"
    )
    assert "2026-05-18" in current_focus
    assert "presidio pin" in current_focus
    assert "BILTIQ-002" in current_focus


def test_manual_section_survives_curator_run(tmp_repo: Path) -> None:
    """Manual section byte-equal before/after 1 curator run (AC3, AC6c)."""
    mem = _memory(tmp_repo)
    before_manual = _extract_manual_block(mem.read_text(encoding="utf-8"))

    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": ["x"], "doing": [], "blockers": []},
    )
    assert run([]) == 0

    after_manual = _extract_manual_block(mem.read_text(encoding="utf-8"))
    assert before_manual == after_manual, "manual section must survive byte-equal"


def test_manual_section_survives_repeated_runs(tmp_repo: Path) -> None:
    """Manual section unchanged across 3 curator runs (AC3 idempotency)."""
    mem = _memory(tmp_repo)
    before_manual = _extract_manual_block(mem.read_text(encoding="utf-8"))

    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": ["x"], "doing": [], "blockers": []},
    )
    write_event(
        "commit_metadata",
        {"sha": "abc", "task_id": None, "files_touched": ["scripts/x.py"]},
    )
    write_event(
        "reflect_note",
        {"task_id": "BILTIQ-003", "what_went_well": [], "what_broke": []},
    )

    for _ in range(3):
        assert run([]) == 0

    after_manual = _extract_manual_block(mem.read_text(encoding="utf-8"))
    assert before_manual == after_manual


def test_missing_auto_marker_fails_closed(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Remove auto:current_focus:end → exit 1, stderr error JSON, MEMORY.md unchanged (Risk R1)."""
    mem = _memory(tmp_repo)
    broken = mem.read_text(encoding="utf-8").replace(
        "<!-- auto:current_focus:end -->", ""
    )
    mem.write_text(broken, encoding="utf-8")

    write_event(
        "standup_post",
        {"date": "2026-05-18", "did": [], "doing": [], "blockers": []},
    )

    assert run([]) == 1

    captured = capsys.readouterr()
    err = json.loads(captured.err.strip())
    assert err["error"] == "missing_marker"
    assert err["marker"] == "auto:current_focus"

    assert mem.read_text(encoding="utf-8") == broken


def test_missing_manual_marker_fails_closed(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Symmetric: remove manual:end → exit 1 with marker='manual', MEMORY.md unchanged (AC3)."""
    mem = _memory(tmp_repo)
    broken = mem.read_text(encoding="utf-8").replace("<!-- manual:end -->", "")
    mem.write_text(broken, encoding="utf-8")

    assert run([]) == 1

    captured = capsys.readouterr()
    err = json.loads(captured.err.strip())
    assert err["error"] == "missing_marker"
    assert err["marker"] == "manual"

    assert mem.read_text(encoding="utf-8") == broken


def test_unknown_event_type_skipped_not_failed(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Writer accepts unknown event_type; curator counts it in events_seen, skips projection (AC4, AC6e)."""
    write_event("future_thing", {"experimental": True})

    assert run([]) == 0

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip())
    assert stats["events_seen"] == 1
    assert stats["events_projected"] == 0
    assert stats["sections_written"] == []


def test_higher_schema_version_skipped(
    tmp_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Forward-compat: schema_version > CURATOR_SUPPORTED_VERSION is counted but not projected."""
    stream = tmp_repo / STREAM_RELATIVE_PATH
    stream.write_text(
        json.dumps({
            "schema_version": 2,
            "ts": "2027-01-01T00:00:00+00:00",
            "event_type": "standup_post",
            "payload": {"date": "2027-01-01", "did": [], "doing": [], "blockers": []},
        }) + "\n",
        encoding="utf-8",
    )

    assert run([]) == 0

    captured = capsys.readouterr()
    stats = json.loads(captured.out.strip())
    assert stats["events_seen"] == 1
    assert stats["events_projected"] == 0

    current_focus = _extract_auto_block(
        _memory(tmp_repo).read_text(encoding="utf-8"), "current_focus"
    )
    assert "2027-01-01" not in current_focus


@pytest.mark.skipif(
    not os.environ.get("BILTIQ_PERF_TEST"),
    reason="perf gate; set BILTIQ_PERF_TEST=1 to enable",
)
def test_curator_under_200ms_for_1000_events(tmp_repo: Path) -> None:
    """Curator under the 200ms budget for 1000 events (AC6b smoke; design says ~10k headroom)."""
    for i in range(1000):
        write_event(
            "standup_post",
            {"date": "2026-05-18", "did": [f"task {i}"], "doing": [], "blockers": []},
        )

    start = time.perf_counter()
    exit_code = run([])
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert exit_code == 0
    assert elapsed_ms < 200, f"curator took {elapsed_ms:.1f} ms, budget is 200 ms"
