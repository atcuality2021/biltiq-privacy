"""Memory-spine writer — append structured events to the per-machine JSONL stream.

Public API: ``write_event(event_type, payload)``.

Atomic-append contract: a single ``os.write()`` against an ``O_APPEND`` fd.
POSIX guarantees the write is atomic against concurrent appenders for
payloads under ``PIPE_BUF`` (4 KiB on Linux). The writer enforces that cap
via ``MemoryEventTooLargeError`` to preserve the guarantee.

Repo-root resolution order:
  1. ``os.environ["BILTIQ_REPO_ROOT"]`` (used by tests).
  2. Walk up from this file looking for a ``.git/`` or ``AGENT_RULES.md`` marker.

No network, no subprocess, no other env vars. See ``docs/adr/0001-memory-spine-pattern.md``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

SCHEMA_VERSION: Final[int] = 1
PIPE_BUF: Final[int] = 4096
STREAM_RELATIVE_PATH: Final[str] = ".biltiq/memory-stream.jsonl"


class MemoryEventTooLargeError(ValueError):
    """Encoded event line exceeds PIPE_BUF (4096 bytes)."""


def _resolve_repo_root() -> Path:
    env_root = os.environ.get("BILTIQ_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    here = Path(__file__).resolve()
    for ancestor in (here, *here.parents):
        if (ancestor / ".git").exists() or (ancestor / "AGENT_RULES.md").exists():
            return ancestor
    raise RuntimeError(
        "Cannot resolve repo root: no BILTIQ_REPO_ROOT env var and no "
        ".git/ or AGENT_RULES.md marker found walking up from "
        f"{here}"
    )


def write_event(event_type: str, payload: dict[str, Any]) -> None:
    """Append one event to ``.biltiq/memory-stream.jsonl``.

    Raises:
      ValueError: ``event_type`` is empty, or ``payload`` is not a dict.
      TypeError: ``payload`` contains non-JSON-serialisable values.
      MemoryEventTooLargeError: encoded line exceeds ``PIPE_BUF`` (4096 bytes).
      OSError: bubbled up unchanged from the filesystem layer.
    """
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("event_type must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    event = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    line = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(line) > PIPE_BUF:
        raise MemoryEventTooLargeError(
            f"event_type={event_type!r} encoded to {len(line)} bytes > PIPE_BUF ({PIPE_BUF})"
        )

    stream_path = _resolve_repo_root() / STREAM_RELATIVE_PATH
    stream_path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(stream_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        written = os.write(fd, line)
        if written != len(line):
            logger.warning(
                "short write to %s: wrote %d of %d bytes",
                stream_path,
                written,
                len(line),
            )
    finally:
        os.close(fd)
