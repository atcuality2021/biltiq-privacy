"""Tests for vendored ``scripts/_memory_writer.py`` — BILTIQ-006 AC1, AC5, AC11.

Ports the surface of plugin v1.10.1 ``tests/spine/test_writer.py`` to this
repo. Test names follow plan.html § Step 3 verbatim (which differ from the
plugin's by-purpose names — the plan groups by AC, the plugin groups by
contract clause).

Ships its own hermetic fixtures (``_hermetic`` + ``repo``) rather than
relying on the repo conftest's ``tmp_repo`` fixture: the conftest fixture
sets ``BILTIQ_REPO_ROOT`` (v1.6 env var), but v1.10.1 ``_memory_writer.py``
reads ``CLAUDE_PROJECT_DIR`` via ``scripts/_paths._resolve_repo_root``. The
conftest fixture remains in use by the curator tests (file-level skipped at
Step 3, deleted at Step 5).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import _memory_writer as mw


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each test runs against a fresh tmp HOME, clean caches, and a clean env.

    Mirrors plugin tests/spine/test_writer.py ``_hermetic``. Also drops
    ``BILTIQ_REPO_ROOT`` in case the repo conftest's ``tmp_repo`` fixture
    leaks via autouse ordering (defence-in-depth — writer ignores it, but
    silencing the leak removes a future foot-gun).
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("BILTIQ_AUTO_TRACK", raising=False)
    monkeypatch.delenv("BILTIQ_AUTO_TRACK_FULL_PROMPTS", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("BILTIQ_REPO_ROOT", raising=False)
    mw._schema_cache.clear()
    mw._compliance_cache.clear()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty repo root; ``.biltiq/`` is scaffolded by the writer on demand."""
    r = tmp_path / "repo"
    r.mkdir()
    return r


def _read_lines(repo_root: Path) -> list[dict[str, Any]]:
    stream = repo_root / ".biltiq" / "memory-stream.jsonl"
    if not stream.is_file():
        return []
    return [
        json.loads(line)
        for line in stream.read_text("utf-8").splitlines()
        if line.strip()
    ]


# AC1, AC5 — happy path: returns True, JSONL line appended with flat payload.
def test_write_event_returns_true_on_valid_payload(repo: Path) -> None:
    """v1.10.1 line shape is flat (``{schema, event_type, ts, ...payload}``),
    not nested under a ``payload`` key as v1.6 did. AC1 contract."""
    ok = mw.write_event(
        "commit",
        {"hash": "abc1234", "msg": "fix thing", "files": []},
        repo_root=str(repo),
    )
    assert ok is True
    rows = _read_lines(repo)
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == "v1"
    assert row["event_type"] == "commit"
    assert row["hash"] == "abc1234"
    assert row["files"] == []
    assert "ts" in row
    # No nested 'payload' key — v1.10.1 flattens.
    assert "payload" not in row


# AC5, AC11 — unknown event_type rejected silently.
def test_write_event_returns_false_on_unknown_event_type(repo: Path) -> None:
    """``not_a_real_type`` has no schema file; writer returns False, no append."""
    ok = mw.write_event("not_a_real_type", {}, repo_root=str(repo))
    assert ok is False
    assert _read_lines(repo) == []


# AC5 — schema-validation reject path on a known event_type.
def test_write_event_returns_false_on_schema_invalid_payload(repo: Path) -> None:
    """commit.hash must match ``^[0-9a-f]{7,40}$``; an int fails the type
    constraint and the validator emits an error. Plan literal said
    ``{"sha": 123}``, but v1.10.1 commit schema has no ``sha`` field — it
    has ``hash``. ``{"hash": 123}`` honors the plan's intent (type-invalid
    required field) more directly than ``{"sha": 123}`` (which would also
    reject, but via the ``additionalProperties: false`` path — a different
    rejection mechanism than the test name suggests)."""
    ok = mw.write_event(
        "commit",
        {"hash": 123, "msg": "ok"},
        repo_root=str(repo),
    )
    assert ok is False
    assert _read_lines(repo) == []


# AC5 — privacy: prompt-field truncation default + env-override.
def test_write_event_truncates_prompt_fields(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    """``yesterday_summary`` is in ``PROMPT_FIELDS``; a 500-char value
    truncates to ``DEFAULT_TRUNCATE_LEN`` + ``...[truncated]`` suffix.
    ``BILTIQ_AUTO_TRACK_FULL_PROMPTS=on`` skips truncation entirely.

    Note on schema interaction: standup_post.yesterday_summary has
    ``maxLength: 1000``, so a 500-char value passes validation. The
    truncation runs after validation, so the on-disk value reflects
    truncation but the validator never sees the 200-char form."""
    long_summary = "x" * 500
    ok = mw.write_event(
        "standup_post",
        {"today_task": "BILTIQ-006", "yesterday_summary": long_summary},
        repo_root=str(repo),
    )
    assert ok is True
    row = _read_lines(repo)[0]
    expected_len = mw.DEFAULT_TRUNCATE_LEN + len("...[truncated]")
    assert len(row["yesterday_summary"]) == expected_len
    assert row["yesterday_summary"].endswith("...[truncated]")

    monkeypatch.setenv("BILTIQ_AUTO_TRACK_FULL_PROMPTS", "on")
    ok = mw.write_event(
        "standup_post",
        {"today_task": "BILTIQ-006", "yesterday_summary": long_summary},
        repo_root=str(repo),
    )
    assert ok is True
    rows = _read_lines(repo)
    assert len(rows) == 2
    assert rows[1]["yesterday_summary"] == long_summary


# AC5 — fcntl.flock serialises concurrent appenders.
def test_write_event_fcntl_flock_serialises_concurrent_writers(repo: Path) -> None:
    """Two threads × 50 events → 100 JSON-valid lines, no interleave.

    The writer holds ``fcntl.flock(LOCK_EX)`` around the f.write/f.flush; the
    POSIX ``open(mode='a')`` already grants O_APPEND atomicity, but the lock
    is belt-and-braces against partial writes on systems where O_APPEND's
    atomicity guarantee is per-write not per-line. With both, 100 valid lines
    is the contract."""
    n_threads = 2
    n_per_thread = 50

    def worker(thread_id: int) -> None:
        for i in range(n_per_thread):
            mw.write_event(
                "commit",
                {"hash": f"{thread_id:02x}{i:05x}", "msg": f"t{thread_id} i{i}"},
                repo_root=str(repo),
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = _read_lines(repo)
    assert len(rows) == n_threads * n_per_thread
    # Each row's hash is unique-per-(thread, i); de-duplication confirms no
    # bytes interleaved into half-finished records.
    seen = {row["hash"] for row in rows}
    assert len(seen) == n_threads * n_per_thread


# AC5 — kill-switch contract: BILTIQ_AUTO_TRACK=off is silent True.
def test_write_event_silent_no_op_under_BILTIQ_AUTO_TRACK_off(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    """Disable returns True (silent success contract — mirrors
    ``scripts/biltiq-auto-log.sh``); ``.biltiq/`` is NOT created."""
    monkeypatch.setenv("BILTIQ_AUTO_TRACK", "off")
    ok = mw.write_event(
        "commit",
        {"hash": "abc1234", "msg": "x"},
        repo_root=str(repo),
    )
    assert ok is True
    assert not (repo / ".biltiq").exists()
    assert _read_lines(repo) == []


# AC5, AC8 — never-raises defensive contract.
def test_write_event_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The plan literal example ``{"x": object()}`` cannot reach the
    json.dumps layer — v1.10.1 schemas have ``additionalProperties: false``
    so the validator rejects the unknown ``x`` key before serialisation runs.
    The actual never-raises contract is best exercised by forcing the
    filesystem write to fail (OSError path of the outer try/except).

    Point ``repo_root`` at a regular file pretending to be a directory; the
    writer's ``biltiq_dir.mkdir(parents=True, exist_ok=True)`` raises
    NotADirectoryError (an OSError subclass); the outer ``except Exception``
    catches it, logs to stderr, returns False — never raises to the caller.

    Skipped on platforms where the chosen file path is unavailable; the
    test is contract-shaped (never raises under hostile filesystem),
    portability is secondary."""
    bogus_path = Path("/proc/1/oom_score")
    if not bogus_path.exists() or bogus_path.is_dir():
        pytest.skip("test relies on a file masquerading as a dir (Linux /proc); skip on this platform")
    try:
        ok = mw.write_event(
            "commit",
            {"hash": "abc1234", "msg": "x"},
            repo_root=str(bogus_path),
        )
    except Exception as exc:  # pragma: no cover — contract violation
        pytest.fail(f"write_event raised {type(exc).__name__}: {exc}")
    assert ok is False


# AC11 — writer-side v1.6 back-compat reject.
def test_write_event_rejects_v1_6_standup_post_payload(repo: Path) -> None:
    """v1.6 ``standup_post`` payload was ``{date, did, doing, blockers}``.
    v1.10.1 ``standup_post`` schema requires ``today_task`` (envelope aside)
    and has ``additionalProperties: false`` — ``date`` and ``doing`` are
    unknown fields; ``today_task`` is missing. The writer rejects cleanly:
    returns False, no exception, no line written. Companion to
    ``test_curator_back_compat_v1_6_events`` in plan Step 5 (curator-side
    AC11): the writer refuses NEW emits of v1.6 shape going forward; the
    curator tolerates historical v1.6 lines already on disk."""
    try:
        ok = mw.write_event(
            "standup_post",
            {"date": "2026-05-18", "doing": "BILTIQ-006"},
            repo_root=str(repo),
        )
    except Exception as exc:  # pragma: no cover — never-raises contract
        pytest.fail(
            f"write_event raised on v1.6 payload: {type(exc).__name__}: {exc}"
        )
    assert ok is False
    assert _read_lines(repo) == []
