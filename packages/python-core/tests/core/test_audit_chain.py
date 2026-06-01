# SPDX-License-Identifier: MIT
"""Behavioural + tamper-evidence tests for ``biltiq_privacy.core.audit_chain``.

Pins the BILTIQ-010 acceptance criteria:

* **AC1** — ``append_row`` commits a row's ``hash`` to ``(prev_hash, payload)``
  via the shared ``doc_hasher.hash_text`` primitive, storing inputs verbatim.
* **AC2** — ``verify_chain`` is tamper-evident: a mutated payload, a corrupted
  stored hash, and a reordered/deleted row are each detected at the right
  first-broken index, and the function reports rather than raises.
* **AC4** — hashing is deterministic and canonical: payload key insertion order
  is irrelevant, and a committed golden vector pins the cross-language recipe.
* **AC5** — multi-row chains verify; empty and single-row chains are edge cases.

All payloads are synthetic (DPDP 2023 §4) — no real identifiers.
"""
from __future__ import annotations

import copy
import json

import pytest

from biltiq_privacy.core.audit_chain import (
    GENESIS_PREV_HASH,
    ChainedRow,
    JsonValue,
    append_row,
    verify_chain,
)
from biltiq_privacy.core.doc_hasher import hash_text


def _build_chain(payloads: list[dict[str, JsonValue]]) -> list[ChainedRow]:
    """Thread ``payloads`` into a valid chain, genesis-anchored."""
    rows: list[ChainedRow] = []
    prev = GENESIS_PREV_HASH
    for payload in payloads:
        row = append_row(prev, payload)
        rows.append(row)
        prev = row["hash"]
    return rows


def test_append_row_commits_to_prev_and_payload() -> None:
    """``append_row`` returns a 3-key row whose hash commits to its inputs (AC1)."""
    payload: dict[str, JsonValue] = {"action": "anonymise", "entity_count": 3}
    row = append_row(GENESIS_PREV_HASH, payload)

    assert set(row) == {"prev_hash", "payload", "hash"}
    assert row["prev_hash"] == GENESIS_PREV_HASH
    assert row["payload"] == payload  # stored verbatim, not mutated
    # Independently recompute the commitment via the documented recipe.
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert row["hash"] == hash_text(GENESIS_PREV_HASH + canonical)
    assert len(row["hash"]) == 64


def test_multi_row_chain_verifies_valid() -> None:
    """A correctly threaded multi-row chain verifies as intact (AC2, AC5)."""
    rows = _build_chain([{"i": 1}, {"i": 2}, {"i": 3}])
    assert verify_chain(rows) == {"valid": True, "first_broken_index": None}


def test_mutated_middle_payload_detected_at_index() -> None:
    """Mutating a middle row's payload is detected at that row (AC2, AC5)."""
    rows = _build_chain([{"i": 1}, {"i": 2}, {"i": 3}])
    tampered = copy.deepcopy(rows)
    tampered[1]["payload"]["i"] = 99  # synthetic mutation

    assert verify_chain(tampered) == {"valid": False, "first_broken_index": 1}


def test_mutated_hash_detected() -> None:
    """Corrupting a row's stored hash is detected at that row (AC2).

    Distinct from the payload path: here the payload is untouched but the
    stored ``hash`` no longer matches the recompute.
    """
    rows = _build_chain([{"i": 1}, {"i": 2}, {"i": 3}])
    tampered = copy.deepcopy(rows)
    tampered[2]["hash"] = "f" * 64

    assert verify_chain(tampered) == {"valid": False, "first_broken_index": 2}


def test_reordered_or_deleted_row_detected_via_link() -> None:
    """Deleting a middle row breaks the prev_hash link of its successor (AC2)."""
    rows = _build_chain([{"i": 1}, {"i": 2}, {"i": 3}])
    without_middle = [rows[0], rows[2]]  # row[2].prev_hash points at the gone row[1]

    # row[2] now sits at index 1; its prev_hash != row[0].hash -> break at 1.
    assert verify_chain(without_middle) == {"valid": False, "first_broken_index": 1}


def test_bad_genesis_detected_at_index_0() -> None:
    """A first row whose prev_hash is not the genesis sentinel breaks at 0 (AC2)."""
    row = append_row("a" * 64, {"i": 1})  # wrong parent for row 0
    assert verify_chain([row]) == {"valid": False, "first_broken_index": 0}


def test_empty_chain_is_vacuously_valid() -> None:
    """An empty chain verifies valid without raising (AC5 edge case)."""
    assert verify_chain([]) == {"valid": True, "first_broken_index": None}


def test_single_valid_row_verifies() -> None:
    """A single genesis-anchored row verifies valid (AC5 edge case)."""
    rows = _build_chain([{"only": "row"}])
    assert verify_chain(rows) == {"valid": True, "first_broken_index": None}


def test_canonical_json_key_order_determinism() -> None:
    """Key insertion order does not change the row hash (AC4).

    ``sort_keys=True`` makes the canonical byte image order-independent, so two
    semantically equal payloads built in different orders commit identically.
    """
    forward = append_row(GENESIS_PREV_HASH, {"a": 1, "b": 2, "c": 3})
    reverse = append_row(GENESIS_PREV_HASH, {"c": 3, "b": 2, "a": 1})
    assert forward["hash"] == reverse["hash"]


def test_golden_vector_pins_cross_language_recipe() -> None:
    """A fixed synthetic payload commits to a pinned digest (AC4).

    This is the cross-language reproduction anchor: the native Node/PHP/Go SDKs
    (and BILTIQ-011/012) must reproduce this exact hex digest for the same
    payload. A change here means the commitment recipe drifted — see
    ``docs/adr/0005-audit-chain-canonical-serialization.md``.
    """
    payload: dict[str, JsonValue] = {
        "action": "anonymise",
        "entity_count": 3,
        "timestamp": "2026-06-01T00:00:00Z",
    }
    row = append_row(GENESIS_PREV_HASH, payload)
    assert (
        row["hash"]
        == "b94c22acea08c71efd775944938842370416784b4bf691a57e25036a35855b65"
    )


def test_append_row_rejects_non_serialisable_payload() -> None:
    """A non-JSON-serialisable payload raises the stdlib ``TypeError`` (AC1).

    The library defines no bespoke exception for this; ``json.dumps`` raising
    ``TypeError`` is the documented rejection path.
    """
    with pytest.raises(TypeError):
        append_row(GENESIS_PREV_HASH, {"bad": {1, 2, 3}})  # type: ignore[dict-item]  # intentionally non-JSON value
