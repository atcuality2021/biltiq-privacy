# SPDX-License-Identifier: MIT
"""Pure, tamper-evident audit hash-chain.

Two stateless free functions (:func:`append_row`, :func:`verify_chain`) plus a
documented genesis sentinel, ported from the CDSCO-RegAI internal codebase
(``backend/modules/audit.py``) as a productisation step for the OSS
``biltiq-privacy`` SDK. There is no runtime dependency on CDSCO-RegAI.

The original bound the hash-chain algorithm to an async SQLAlchemy session and
wrote rows to a database. Only the ~50-line *commitment* core belongs in a leaf
library, so the persistence coupling is dropped entirely: these functions
compute and verify rows, and the consumer persists them however it likes
(JSON file, Postgres, object store). This module imports no database driver,
session, web framework, or LLM client — purity is the contract.

Commitment recipe (the cross-language contract — see
``docs/adr/0005-audit-chain-canonical-serialization.md``)::

    canonical = json.dumps(payload, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    row_hash  = hash_text(prev_hash + canonical)

``prev_hash`` is always exactly 64 hex characters (a SHA-256 hex digest, or the
all-zero :data:`GENESIS_PREV_HASH` sentinel for the first row), so the boundary
between it and the canonical payload in the pre-image is unambiguous and needs
no delimiter. Timestamps are not generated here — a caller that wants one passes
it as an ordinary ``payload`` field, keeping every row deterministic and
reproducible offline.
"""
from __future__ import annotations

import json
from typing import Final, TypeAlias, TypedDict

from biltiq_privacy.core.doc_hasher import hash_text

# Recursive JSON value alias — keeps ``payload`` fully typed without ``Any``.
# The ``TypeAlias`` assignment form (not the PEP 695 ``type X = ...`` statement)
# is used deliberately: the ``type`` statement is 3.12+ grammar and this package
# floors at ``requires-python >=3.11``, where it raises ``SyntaxError`` at import.
# The ``|`` union operator and the ``"JsonValue"`` string forward-refs are both
# 3.11-safe at runtime.
JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

#: ``prev_hash`` of the first row in a chain — 64 zero hex chars ("null parent").
#: Same width and alphabet as a real SHA-256 hex digest, so row 0 needs no
#: special-casing in the hashing path, and not a reachable digest for any
#: practical input, so it cannot be forged as a mid-chain link.
GENESIS_PREV_HASH: Final[str] = "0" * 64


class ChainedRow(TypedDict):
    """One link in the audit chain.

    ``prev_hash`` is the preceding row's :data:`ChainedRow.hash`, or
    :data:`GENESIS_PREV_HASH` for the first row. ``payload`` is the opaque,
    caller-owned event mapping (any JSON-serialisable fields, including a
    caller-supplied ``timestamp``). ``hash`` commits to both — see the module
    docstring for the recipe.
    """

    prev_hash: str
    payload: dict[str, JsonValue]
    hash: str


class VerifyReport(TypedDict):
    """Result of :func:`verify_chain`.

    ``valid`` is ``True`` for an intact chain (the empty chain is vacuously
    valid); ``first_broken_index`` is ``None`` when valid, else the index of the
    first row that fails either the hash-recompute or the link check.
    """

    valid: bool
    first_broken_index: int | None


def _canonical_json(payload: dict[str, JsonValue]) -> str:
    """Serialise ``payload`` to the canonical, cross-language byte image.

    ``sort_keys=True`` fixes key order regardless of insertion order;
    ``separators=(",", ":")`` strips insignificant whitespace; ``ensure_ascii``
    is ``False`` so non-ASCII text is emitted verbatim (utf-8) rather than
    ``\\uXXXX``-escaped. Raises the stdlib :class:`TypeError` if ``payload``
    contains a value JSON cannot represent.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def append_row(prev_hash: str, payload: dict[str, JsonValue]) -> ChainedRow:
    """Compute and return the next chained row.

    The row's ``hash`` is ``hash_text(prev_hash + _canonical_json(payload))``,
    reusing the engine's shared SHA-256 primitive. Pass :data:`GENESIS_PREV_HASH`
    as ``prev_hash`` for the first row and the previous row's ``hash`` thereafter.

    Pure: no stored state, no clock read, no I/O. The inputs are stored verbatim
    and not mutated. Raises the stdlib :class:`TypeError` (from ``json.dumps``)
    if ``payload`` is not JSON-serialisable — that native exception is the
    rejection path; the library defines no bespoke exception for it.
    """
    row_hash = hash_text(prev_hash + _canonical_json(payload))
    return ChainedRow(prev_hash=prev_hash, payload=payload, hash=row_hash)


def verify_chain(rows: list[ChainedRow]) -> VerifyReport:
    """Recompute every row's hash and validate the ``prev_hash`` links.

    Walks the chain once in order. A row at index ``i`` is broken if either its
    recomputed hash differs from its stored ``hash`` (detects any mutation of
    ``payload`` or ``hash``) or its ``prev_hash`` does not match the expected
    parent (:data:`GENESIS_PREV_HASH` for row 0, the prior row's ``hash``
    otherwise — detects reordering, insertion, and deletion). Returns at the
    first broken index.

    Returns ``{valid: True, first_broken_index: None}`` for an intact chain
    (including the empty chain, which is vacuously valid) and
    ``{valid: False, first_broken_index: i}`` at the first break. Tampering is a
    normal, reported outcome — this function never raises on it.
    """
    expected_prev = GENESIS_PREV_HASH
    for index, row in enumerate(rows):
        recomputed = hash_text(row["prev_hash"] + _canonical_json(row["payload"]))
        if recomputed != row["hash"] or row["prev_hash"] != expected_prev:
            return VerifyReport(valid=False, first_broken_index=index)
        expected_prev = row["hash"]
    return VerifyReport(valid=True, first_broken_index=None)
