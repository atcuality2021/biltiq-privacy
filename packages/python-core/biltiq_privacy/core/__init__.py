# SPDX-License-Identifier: MIT
"""Core engine primitives.

Holds the stateless hashing helpers (``doc_hasher``), the key-bound
``Pseudonymiser`` (entity → HMAC token), the rule-based ``generaliser``
rollups (age/date/location/phone/Aadhaar/PAN + the ``generalise_text``
dispatch), and the library exception home (``exceptions``). ``audit_chain``
lands in a later Phase A task (BILTIQ-010).

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
from biltiq_privacy.core.generaliser import (
    GeneralisationSpan,
    generalise_aadhaar,
    generalise_age,
    generalise_date,
    generalise_location,
    generalise_pan,
    generalise_phone,
    generalise_text,
)
from biltiq_privacy.core.pseudonymiser import (
    AuditRecord,
    Detection,
    Pseudonymiser,
)

__all__ = [
    "AuditRecord",
    "Detection",
    "GeneralisationSpan",
    "HMACKeyRequiredError",
    "Pseudonymiser",
    "generalise_aadhaar",
    "generalise_age",
    "generalise_date",
    "generalise_location",
    "generalise_pan",
    "generalise_phone",
    "generalise_text",
    "hash_document",
    "hash_text",
    "hmac_pseudonymise",
]
