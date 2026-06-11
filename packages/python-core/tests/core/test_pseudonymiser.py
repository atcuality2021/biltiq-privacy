# SPDX-License-Identifier: MIT
"""Tests for ``biltiq_privacy.core.pseudonymiser`` (BILTIQ-007 Step 3).

Characterization suite pinning CDSCO behaviour against fixed inputs:
token form ``[TYPE_<hex>]`` (AC2), configurable ``token_length`` (AC2),
determinism + key-sensitivity (AC3), multi-entity end→start replacement
with restored audit order and the five CDSCO audit keys (AC2/AC5), and
fail-fast ``HMACKeyRequiredError`` on an empty key at construction (AC4).

Golden tokens are hardcoded (computed externally with the fixture key) so
the suite is a true behaviour gate, not a recomputation of the
implementation.
"""
from __future__ import annotations

import pytest

from biltiq_privacy.core.exceptions import HMACKeyRequiredError
from biltiq_privacy.core.pseudonymiser import (
    AuditRecord,
    Detection,
    Pseudonymiser,
)

# Golden values for fixture key b"biltiq-privacy-test-hmac-key-32b".
_TOKEN_PERSON_RAJESH = "[PERSON_21a8f75c]"
_TOKEN_PAN = "[IN_PAN_cbff8792]"

# A two-entity sentence with known offsets.
_TEXT = "Patient Rajesh Kumar, PAN ABCDE1234F, visited."
_DETECTIONS: list[Detection] = [
    {"entity_type": "PERSON", "text": "Rajesh Kumar", "start": 8, "end": 20, "score": 0.95},
    {"entity_type": "IN_PAN", "text": "ABCDE1234F", "start": 26, "end": 36, "score": 0.99},
]
_EXPECTED_TEXT = "Patient [PERSON_21a8f75c], PAN [IN_PAN_cbff8792], visited."


def test_make_token_format(hmac_key: bytes) -> None:
    """Token matches ``[TYPE_<8 hex>]`` at the default length (AC2)."""
    p = Pseudonymiser(key=hmac_key)
    token = p.make_token("PERSON", "Rajesh Kumar")
    assert token == _TOKEN_PERSON_RAJESH
    # Structural: [TYPE_ + 8 hex + ].
    assert token.startswith("[PERSON_") and token.endswith("]")
    assert len(token) == len("[PERSON_") + 8 + 1


def test_token_length_configurable(hmac_key: bytes) -> None:
    """``token_length=12`` keeps 12 hex chars of the digest (AC2)."""
    p = Pseudonymiser(key=hmac_key)
    token = p.make_token("PERSON", "Rajesh Kumar", token_length=12)
    assert token == "[PERSON_21a8f75c95ec]"


def test_token_deterministic_per_key(hmac_key: bytes) -> None:
    """Same value+key → same token; a different key → a different token (AC3)."""
    p1 = Pseudonymiser(key=hmac_key)
    p2 = Pseudonymiser(key=hmac_key)
    assert p1.make_token("PERSON", "Rajesh Kumar") == p2.make_token("PERSON", "Rajesh Kumar")

    other = Pseudonymiser(key=b"a-different-key")
    assert other.make_token("PERSON", "Rajesh Kumar") != _TOKEN_PERSON_RAJESH


def test_pseudonymise_text_multi_entity(hmac_key: bytes) -> None:
    """Multiple spans replaced; offsets stay valid; audit restored in order (AC2, AC5)."""
    p = Pseudonymiser(key=hmac_key)
    result, audit = p.pseudonymise_text(_TEXT, _DETECTIONS)

    assert result == _EXPECTED_TEXT

    # Audit list is restored to original document order (PERSON before PAN).
    assert [a["entity_type"] for a in audit] == ["PERSON", "IN_PAN"]
    # The five CDSCO audit keys, exactly.
    assert set(audit[0].keys()) == {
        "entity_type",
        "pseudonym_token",
        "position_start",
        "position_end",
        "confidence",
    }
    first: AuditRecord = audit[0]
    assert first["pseudonym_token"] == _TOKEN_PERSON_RAJESH
    assert first["position_start"] == 8
    assert first["position_end"] == 20
    assert first["confidence"] == 0.95
    assert audit[1]["pseudonym_token"] == _TOKEN_PAN


def test_pseudonymise_text_empty_detections(hmac_key: bytes) -> None:
    """No detections → text unchanged, empty audit list (success edge path)."""
    p = Pseudonymiser(key=hmac_key)
    result, audit = p.pseudonymise_text(_TEXT, [])
    assert result == _TEXT
    assert audit == []


@pytest.mark.parametrize("empty_key", [b"", ""])
def test_empty_key_raises(empty_key: bytes | str) -> None:
    """An empty key raises ``HMACKeyRequiredError`` at construction (AC4)."""
    with pytest.raises(HMACKeyRequiredError):
        Pseudonymiser(key=empty_key)
