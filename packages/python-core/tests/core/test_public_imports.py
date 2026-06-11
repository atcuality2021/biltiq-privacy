# SPDX-License-Identifier: MIT
"""Public-surface import tests for ``biltiq_privacy.core`` (BILTIQ-007 Step 4).

Pins AC2: the convenience re-exports resolve from the package root and
``__all__`` advertises exactly the intended surface, so downstream tasks
(BILTIQ-011/012) can rely on a stable import path.
"""
from __future__ import annotations

import biltiq_privacy.core as core


def test_public_imports() -> None:
    """Core re-exports resolve from ``biltiq_privacy.core`` (AC2)."""
    from biltiq_privacy.core import (
        GENESIS_PREV_HASH,
        AuditRecord,
        ChainedRow,
        Detection,
        GeneralisationSpan,
        HMACKeyRequiredError,
        MissingNERModelError,
        Pseudonymiser,
        VerifyReport,
        append_row,
        generalise_aadhaar,
        generalise_age,
        generalise_date,
        generalise_location,
        generalise_pan,
        generalise_phone,
        generalise_text,
        hash_document,
        hash_text,
        hmac_pseudonymise,
        verify_chain,
    )

    # Reference each so the import is not flagged as unused and is proven live.
    assert issubclass(HMACKeyRequiredError, ValueError)
    assert issubclass(MissingNERModelError, RuntimeError)
    assert Pseudonymiser.__name__ == "Pseudonymiser"
    assert callable(hash_document)
    assert callable(hash_text)
    assert callable(hmac_pseudonymise)
    assert Detection.__name__ == "Detection"
    assert AuditRecord.__name__ == "AuditRecord"
    assert GeneralisationSpan.__name__ == "GeneralisationSpan"
    assert callable(generalise_age)
    assert callable(generalise_date)
    assert callable(generalise_location)
    assert callable(generalise_phone)
    assert callable(generalise_aadhaar)
    assert callable(generalise_pan)
    assert callable(generalise_text)
    # audit_chain surface (BILTIQ-010): two free functions, two row TypedDicts,
    # and the genesis sentinel — the value is pinned so a drift in the constant
    # (which every chain anchors on) fails here, not silently mid-chain.
    assert callable(append_row)
    assert callable(verify_chain)
    assert ChainedRow.__name__ == "ChainedRow"
    assert VerifyReport.__name__ == "VerifyReport"
    assert GENESIS_PREV_HASH == "0" * 64


def test_all_matches_exported_surface() -> None:
    """``__all__`` lists exactly the symbols the package re-exports (AC2)."""
    assert sorted(core.__all__) == [
        "AuditRecord",
        "ChainedRow",
        "Detection",
        "GENESIS_PREV_HASH",
        "GeneralisationSpan",
        "HMACKeyRequiredError",
        "MissingNERModelError",
        "Pseudonymiser",
        "VerifyReport",
        "append_row",
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
        "verify_chain",
    ]
    for name in core.__all__:
        assert hasattr(core, name), f"{name} in __all__ but not importable from core"
