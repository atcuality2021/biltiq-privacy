"""Memory-spine curator — project events from the stream into MEMORY.md.

Step 2 scope (this commit): the outer shell — argparse, ``fcntl.flock``
acquisition, stream reading, atomic ``MEMORY.md`` rewrite, and the CLI
exit-code contract. The projection function is a stub returning the file
unchanged. Step 3 replaces the stub with per-event-type projectors and
fail-closed marker handling.

CLI contract (documented in ``docs/specs/BILTIQ-003/design.html``):
  $ python3 scripts/_memory_curator.py [--verbose]
  Exit 0 — success (rewritten, or no-op for empty stream).
  Exit 0 — lock held by another process; stdout: {"skipped": "..."}.
  Exit 1 — fail-closed: missing marker; stderr: {"error": "missing_marker", ...}.
  Exit 2 — unrecoverable I/O; stderr: {"error": "io", "detail": ...}.

On success, stdout is one JSON line:
  {"events_seen": N, "events_projected": M, "sections_written": [...]}
"""

from __future__ import annotations

import sys
from pathlib import Path

# When invoked as `python3 scripts/_memory_curator.py`, Python puts the
# script's parent dir (scripts/) on sys.path[0] — not the repo root — so the
# absolute `from scripts.*` import below cannot resolve. Insert the repo root
# (the parent of this file's parent). No-op under module imports or under
# `python3 -m scripts._memory_curator`, where __package__ is already set.
if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Final, Iterator

from scripts._memory_writer import _resolve_repo_root

logger = logging.getLogger(__name__)

LOCK_RELATIVE_PATH: Final[str] = ".biltiq/.curator.lock"
STREAM_RELATIVE_PATH: Final[str] = ".biltiq/memory-stream.jsonl"
MEMORY_RELATIVE_PATH: Final[str] = "MEMORY.md"
CURATOR_SUPPORTED_VERSION: Final[int] = 1
LOCK_FILE_MODE: Final[int] = 0o600


class CuratorError(Exception):
    """Base error for curator-side failures."""


class MissingMarkerError(CuratorError):
    """Raised when MEMORY.md is missing an expected auto/manual marker pair."""

    def __init__(self, marker: str) -> None:
        super().__init__(f"missing marker: {marker}")
        self.marker = marker


@contextmanager
def _acquire_lock(lock_path: Path) -> Iterator[bool]:
    """Acquire an exclusive non-blocking flock on ``lock_path``.

    Yields ``True`` if the lock was acquired (caller does the work), ``False``
    if another process holds it (caller should print the skipped sentinel and
    exit 0). The fd is unconditionally closed on exit; ``fcntl.flock`` releases
    the lock automatically when the fd closes — including on crash or kill.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, LOCK_FILE_MODE)
    try:
        os.fchmod(fd, LOCK_FILE_MODE)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_events(stream_path: Path) -> list[dict[str, Any]]:
    """Read every JSON-line event in the stream. Skips malformed lines with a WARNING."""
    if not stream_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with stream_path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "skipping malformed line %d in %s: %s",
                    lineno,
                    stream_path,
                    exc,
                )
                continue
            events.append(event)
    return events


def _project_events(
    events: list[dict[str, Any]],
    memory_text: str,
) -> tuple[str, dict[str, Any]]:
    """STUB (Step 2): return ``memory_text`` unchanged + projection stats.

    Step 3 replaces this with real per-event-type projectors and fail-closed
    marker handling (raises :class:`MissingMarkerError` if any auto/manual
    pair is absent from ``memory_text``).
    """
    eligible = [e for e in events if e.get("schema_version", 1) <= CURATOR_SUPPORTED_VERSION]
    stats: dict[str, Any] = {
        "events_seen": len(events),
        "events_projected": 0,
        "sections_written": [],
    }
    del eligible
    return memory_text, stats


def _atomic_write(target: Path, content: str) -> None:
    """Write ``content`` to ``target`` via a sibling temp file + ``os.replace``.

    No partial-write window: readers always see either the old or the new
    file, never a half-written one. Cleans up the temp file if anything
    goes wrong before the replace.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(str(tmp_path), str(target))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def run(argv: list[str] | None = None) -> int:
    """CLI entry. Returns the process exit code (also see module docstring)."""
    parser = argparse.ArgumentParser(
        description="Project memory-spine events into MEMORY.md",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable INFO logging on stderr",
    )
    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    try:
        root = _resolve_repo_root()
    except RuntimeError as exc:
        sys.stderr.write(json.dumps({"error": "io", "detail": str(exc)}) + "\n")
        return 2

    lock_path = root / LOCK_RELATIVE_PATH
    stream_path = root / STREAM_RELATIVE_PATH
    memory_path = root / MEMORY_RELATIVE_PATH

    with _acquire_lock(lock_path) as acquired:
        if not acquired:
            sys.stdout.write(json.dumps({"skipped": "another curator already running"}) + "\n")
            return 0

        try:
            events = _read_events(stream_path)
            current = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        except OSError as exc:
            sys.stderr.write(json.dumps({"error": "io", "detail": str(exc)}) + "\n")
            return 2

        try:
            new_text, stats = _project_events(events, current)
        except MissingMarkerError as exc:
            sys.stderr.write(json.dumps({"error": "missing_marker", "marker": exc.marker}) + "\n")
            return 1

        if new_text != current:
            try:
                _atomic_write(memory_path, new_text)
            except OSError as exc:
                sys.stderr.write(json.dumps({"error": "io", "detail": str(exc)}) + "\n")
                return 2

        sys.stdout.write(json.dumps(stats) + "\n")
        return 0


if __name__ == "__main__":
    sys.exit(run())
