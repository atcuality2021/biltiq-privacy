"""Tests for vendored ``scripts/memory_schemas/`` — BILTIQ-006 AC1.

Each of the 14 vendored Draft-07 JSON schemas must:
  1. parse as JSON,
  2. validate as a well-formed Draft-07 schema (metaschema check), and
  3. self-identify by filename stem in either ``title`` or
     ``properties.event_type.const``.

The disjunction is necessary because ``routing_payload`` is a non-event
schema (M29 AC15 skill-routing payload) and lacks ``event_type`` entirely;
the other 13 are memory-spine event schemas where both fields exist and
match the stem. The curator's ``event_type → schema`` dispatch uses the
``event_type.const`` field where present; ``title`` is the universal
fallback discriminator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "memory_schemas"

SCHEMA_NAMES = [
    "blocker_close",
    "blocker_open",
    "commit",
    "compliance_flag",
    "decision",
    "doctor_install",
    "eod_post",
    "estimate_actual",
    "routing_payload",
    "scan_result",
    "security_flag",
    "standup_post",
    "task_state_change",
    "vllm_quality_warning",
]


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schema_loads_and_is_valid_draft7(name: str) -> None:
    path = SCHEMAS_DIR / f"{name}.json"
    assert path.is_file(), f"vendored schema missing: {path}"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    title = schema.get("title")
    event_const = (
        schema.get("properties", {}).get("event_type", {}).get("const")
    )
    assert name in {title, event_const}, (
        f"filename stem {name!r} matches neither "
        f"title ({title!r}) nor event_type.const ({event_const!r})"
    )
