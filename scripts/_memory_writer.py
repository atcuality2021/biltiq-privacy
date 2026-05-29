# SYNC-HEADER:
#   source: ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_memory_writer.py
#   sha256: 5097c527946c4947c660e6391a5e1e62c8f76b78b29c28d393fee4082c860335
#   synced: 2026-05-29
#   adr:    docs/adr/0004-memory-spine-vendoring.md
# END-SYNC-HEADER
"""scripts/_memory_writer.py — memory-spine writer (BILTIQ-017a Step 2).

Public API:
    write_event(event_type, payload, *, repo_root=None) -> bool

Append a versioned event line to ``<repo>/.biltiq/memory-stream.jsonl`` after
schema validation, on-prem PII stripping, and prompt truncation.

Contract:
    - Returns True on success OR when ``BILTIQ_AUTO_TRACK=off`` (silent no-op,
      matches ``scripts/biltiq-auto-log.sh`` semantics).
    - Returns False on any rejection: unknown event_type, schema-invalid
      payload, jsonschema not installed, I/O failure.
    - Never raises. All failures log to stderr.

Step 2 scope: writer + cooldown-marker for curator. Spawning the actual
curator is deferred to Step 4 (skill extension) + Step 7 (external triggers);
this module lays a ``curator-pending.flag`` when the 60-min cooldown elapses,
which downstream consumers honor.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft7Validator
except ImportError:  # pragma: no cover - tested via stderr-only path
    Draft7Validator = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = SCRIPT_DIR / "memory_schemas"

# Ensure scripts/ is on sys.path so sibling spine modules (`_paths`) resolve
# whether this file is invoked as a CLI script or imported by tests.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _paths import _resolve_repo_root, _repo_hash  # noqa: E402

DEFAULT_TRUNCATE_LEN = 200  # matches hooks/user-prompt-submit/hook.sh
CURATOR_COOLDOWN_SECONDS = 3600  # 60 minutes — design.md § 1
# Threshold trigger per spec § Q3 = Option C: fire curator when ~1000+ events
# have accumulated since the last run, even if the time-cooldown hasn't
# elapsed. Implemented as a byte-size proxy (avg ~250 bytes per event line)
# so the writer's hot path stays a single stat() rather than a line-count
# read of the whole JSONL on every append.
CURATOR_THRESHOLD_BYTES = 250_000

# Free-text fields that may carry user prompt content. Truncated unless
# BILTIQ_AUTO_TRACK_FULL_PROMPTS=on. Drawn from the ten v1 event schemas.
PROMPT_FIELDS = frozenset({
    "msg",
    "message",
    "summary",
    "yesterday_summary",
    "today_task",
    "tomorrow",
    "tech_debt",
    "resolution",
})

VALID_COMPLIANCE_MODES = frozenset({
    "on_prem_required",
    "on_prem_preferred",
    "cloud_ok",
})

_schema_cache: dict[str, dict[str, Any] | None] = {}
_compliance_cache: dict[str, tuple[float, str]] = {}


def _log_warn(msg: str) -> None:
    print(f"[memory_writer] {msg}", file=sys.stderr)


def _state_dir(repo_root: Path) -> Path:
    return Path.home() / ".biltiq-engineering" / _repo_hash(repo_root) / "state"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_schema(event_type: str) -> dict[str, Any] | None:
    """Load the JSON schema for ``event_type`` from SCHEMAS_DIR with caching."""
    if event_type in _schema_cache:
        return _schema_cache[event_type]

    path = SCHEMAS_DIR / f"{event_type}.json"
    if not path.is_file():
        _log_warn(f"unknown event_type '{event_type}' (no schema at {path})")
        _schema_cache[event_type] = None
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        # Narrowed per BILTIQ-020 Step 8. OSError covers file-read failures
        # (permission, disk, vanished). json.JSONDecodeError covers malformed
        # schema files. MemoryError on huge schemas propagates.
        _log_warn(f"failed to load schema for '{event_type}': {exc}")
        _schema_cache[event_type] = None
        return None

    _schema_cache[event_type] = schema
    return schema


def _read_compliance_mode(repo_root: Path) -> str:
    """Parse ``AGENT_RULES.md § Compliance`` and return the declared mode.

    Caches by file mtime so the hot path stays sub-millisecond on repeat calls.
    Defaults to ``on_prem_preferred`` when missing or unparseable, matching
    ``skills/using-biltiq-engineering`` § Compliance mode.
    """
    rules = repo_root / "AGENT_RULES.md"
    cache_key = str(repo_root)
    if not rules.is_file():
        return "on_prem_preferred"

    try:
        mtime = rules.stat().st_mtime
    except OSError:
        return "on_prem_preferred"

    cached = _compliance_cache.get(cache_key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    mode = "on_prem_preferred"
    try:
        text = rules.read_text(encoding="utf-8", errors="replace")
        # Match `**Mode:** \`value\`` or `Mode: value` (case-insensitive),
        # taking the first known compliance token. Backticks optional.
        for m in re.finditer(
            r"(?im)^\*{0,2}\s*mode\s*:\*{0,2}\s*`?(\w+)`?",
            text,
        ):
            token = m.group(1).lower()
            if token in VALID_COMPLIANCE_MODES:
                mode = token
                break
    except (OSError, re.error) as exc:
        # Narrowed per BILTIQ-020 Step 8. OSError covers read failures.
        # re.error covers a malformed regex (defensive — pattern is hard-coded
        # so this is unreachable in practice but cheap to guard).
        _log_warn(f"failed to parse AGENT_RULES.md compliance: {exc}")

    _compliance_cache[cache_key] = (mtime, mode)
    return mode


def _strip_external_api_fields(record: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Remove properties whose schema entry sets ``external_api_response: true``.

    JSON Schema has no native field-level "is this external-API response data"
    bit, so the convention is a top-level annotation on each property:
    ``"properties": {"foo": {"type": "string", "external_api_response": true}}``.
    Schemas opt fields in; on_prem_required strips them.
    """
    props = schema.get("properties", {})
    stripped = dict(record)
    for name, spec in props.items():
        if isinstance(spec, dict) and spec.get("external_api_response") is True:
            stripped.pop(name, None)
    return stripped


def _truncate_prompts(record: dict[str, Any]) -> dict[str, Any]:
    """Truncate free-text fields to DEFAULT_TRUNCATE_LEN unless full-prompt
    capture is explicitly enabled. Mirrors ``hooks/user-prompt-submit/hook.sh``.
    """
    if os.environ.get("BILTIQ_AUTO_TRACK_FULL_PROMPTS", "off") == "on":
        return record
    out: dict[str, Any] = {}
    for k, v in record.items():
        if k in PROMPT_FIELDS and isinstance(v, str) and len(v) > DEFAULT_TRUNCATE_LEN:
            out[k] = v[:DEFAULT_TRUNCATE_LEN] + "...[truncated]"
        else:
            out[k] = v
    return out


def _read_state_float(path: Path) -> float:
    if not path.is_file():
        return 0.0
    try:
        return float(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0.0


def _read_state_int(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def _maybe_trigger_curator(repo_root: Path, jsonl_path: Path) -> None:
    """Lay a ``curator-pending.flag`` if EITHER:
      - 60+ min elapsed since the last curator run, OR
      - ~1000+ events have accumulated since then (byte-size proxy).

    The marker is consumed by the curator skill (Step 4) and by external
    triggers (Step 7: standup + commit hook). Writer-side hot path is
    bounded: stat + two tiny state reads + an empty-file touch + two int
    writes. Stays well under the 50ms trigger-detection cap from spec § Q3.
    """
    try:
        state_dir = _state_dir(repo_root)
        state_dir.mkdir(parents=True, exist_ok=True)
        last_ts_file = state_dir / "last-curator.txt"
        last_bytes_file = state_dir / "last-curator-bytes.txt"
        marker = state_dir / "curator-pending.flag"
        now = time.time()

        last_ts = _read_state_float(last_ts_file)
        last_bytes = _read_state_int(last_bytes_file)
        try:
            current_bytes = jsonl_path.stat().st_size if jsonl_path.is_file() else 0
        except OSError:
            current_bytes = 0

        time_due = (now - last_ts) >= CURATOR_COOLDOWN_SECONDS
        threshold_due = (current_bytes - last_bytes) >= CURATOR_THRESHOLD_BYTES

        if time_due or threshold_due:
            marker.touch(exist_ok=True)
            last_ts_file.write_text(str(int(now)), encoding="utf-8")
            last_bytes_file.write_text(str(current_bytes), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — INTENTIONAL DEFENSIVE NET
        # Per BILTIQ-020 Step 8: this broad catch is intentional. The curator
        # trigger is best-effort; ANY failure here must not propagate into
        # the writer's hot path (write_event must remain "Never raises" per
        # module docstring). The _log_warn already records the type+message
        # for post-mortem.
        _log_warn(f"curator-trigger failed (non-fatal): {exc}")


def write_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    repo_root: str | None = None,
) -> bool:
    """Append a versioned event to ``.biltiq/memory-stream.jsonl``.

    See module docstring for full contract. ``payload`` should NOT include
    ``schema`` or ``event_type`` — those are injected. ``ts`` is auto-stamped
    in UTC if not supplied.
    """
    try:
        if os.environ.get("BILTIQ_AUTO_TRACK", "on") == "off":
            return True  # silent no-op, mirrors biltiq-auto-log.sh

        if Draft7Validator is None:
            _log_warn("jsonschema not installed; cannot validate, dropping event")
            return False

        if not isinstance(payload, dict):
            _log_warn(
                f"payload must be dict, got {type(payload).__name__} for "
                f"event_type='{event_type}'"
            )
            return False

        root = _resolve_repo_root(repo_root)

        schema = _load_schema(event_type)
        if schema is None:
            return False

        # Compose the record: pinned envelope + caller payload (caller can't
        # override schema/event_type; ts auto-fills if absent).
        record: dict[str, Any] = {
            "schema": "v1",
            "event_type": event_type,
            "ts": payload.get("ts") or _now_iso(),
        }
        for k, v in payload.items():
            if k not in {"schema", "event_type"}:
                record[k] = v

        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(record))
        if errors:
            _log_warn(
                f"schema rejected {event_type}: "
                + "; ".join(e.message for e in errors[:3])
            )
            return False

        if _read_compliance_mode(root) == "on_prem_required":
            record = _strip_external_api_fields(record, schema)

        record = _truncate_prompts(record)

        biltiq_dir = root / ".biltiq"
        biltiq_dir.mkdir(parents=True, exist_ok=True)
        stream = biltiq_dir / "memory-stream.jsonl"

        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

        with open(stream, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(line)
                f.flush()
            finally:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

        _maybe_trigger_curator(root, stream)
        return True

    except Exception as exc:  # noqa: BLE001 — INTENTIONAL DEFENSIVE NET
        # Per BILTIQ-020 Step 8: this broad catch is intentional and enforces
        # the module-docstring contract "Never raises". write_event is invoked
        # from hooks (PreToolUse / PostToolUse / UserPromptSubmit / Stop) that
        # cannot tolerate exceptions — a raise here would crash the user's
        # tool call. Any unexpected failure logs to stderr + returns False.
        _log_warn(f"unexpected error writing event '{event_type}': {exc}")
        return False


def append_estimate_actual(
    row: dict[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> bool:
    """Append an estimate-vs-actual row to ``.biltiq/estimates-history.jsonl``.

    Per BILTIQ-022 AC6. Mirrors ``write_event``'s never-raises contract,
    silent-no-op-on-`BILTIQ_AUTO_TRACK=off`, and atomic-append semantics, but
    writes to ``estimates-history.jsonl`` (NOT ``memory-stream.jsonl``) and
    intentionally skips the curator trigger — this file is consumed by
    ``scripts/_estimates_lookup.py``, not the memory curator.

    ``row`` must satisfy ``memory_schemas/estimate_actual.json``. ``schema``
    and ``event_type`` are pinned by this writer; ``ts`` auto-fills in UTC
    if not supplied by the caller.
    """
    try:
        if os.environ.get("BILTIQ_AUTO_TRACK", "on") == "off":
            return True  # silent no-op, mirrors write_event

        if Draft7Validator is None:
            _log_warn("jsonschema not installed; cannot validate, dropping estimate_actual")
            return False

        if not isinstance(row, dict):
            _log_warn(
                f"row must be dict, got {type(row).__name__} for estimate_actual"
            )
            return False

        root = _resolve_repo_root(repo_root)

        schema = _load_schema("estimate_actual")
        if schema is None:
            return False

        record: dict[str, Any] = {
            "schema": "v1",
            "event_type": "estimate_actual",
            "ts": row.get("ts") or _now_iso(),
        }
        for k, v in row.items():
            if k not in {"schema", "event_type"}:
                record[k] = v

        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(record))
        if errors:
            _log_warn(
                "schema rejected estimate_actual: "
                + "; ".join(e.message for e in errors[:3])
            )
            return False

        biltiq_dir = root / ".biltiq"
        biltiq_dir.mkdir(parents=True, exist_ok=True)
        stream = biltiq_dir / "estimates-history.jsonl"

        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

        with open(stream, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(line)
                f.flush()
            finally:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

        # Curator trigger intentionally skipped — estimates-history is read
        # by _estimates_lookup.py, not _memory_curator.py.
        return True

    except Exception as exc:  # noqa: BLE001 — INTENTIONAL DEFENSIVE NET
        # Same contract as write_event: invoked from /biltiq-engineering:reflect
        # closure; an exception here would crash the task-close step. Any
        # unexpected failure logs to stderr + returns False.
        _log_warn(f"unexpected error writing estimate_actual: {exc}")
        return False


__all__ = ["write_event", "append_estimate_actual"]
