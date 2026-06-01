# SPDX-License-Identifier: MIT
"""Core engine primitives.

Holds the stateless hashing helpers (``doc_hasher``), the key-bound
``Pseudonymiser`` (entity → HMAC token), and the library exception home
(``exceptions``). ``generaliser`` and ``audit_chain`` land in later Phase A
tasks (BILTIQ-008 / BILTIQ-010).

Submodule imports remain canonical; the re-exports below are an additive
convenience for a stable ``biltiq_privacy.core`` import surface.
"""
from __future__ import annotations

from biltiq_privacy.core.doc_hasher import (
    hash_document,
    hash_text,
    hmac_pseudonymise,
)
from biltiq_privacy.core.exceptions import HMACKeyRequiredError
from biltiq_privacy.core.pseudonymiser import (
    AuditRecord,
    Detection,
    Pseudonymiser,
)

__all__ = [
    "AuditRecord",
    "Detection",
    "HMACKeyRequiredError",
    "Pseudonymiser",
    "hash_document",
    "hash_text",
    "hmac_pseudonymise",
]
