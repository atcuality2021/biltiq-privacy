# SPDX-License-Identifier: MIT
"""AC3 end-to-end integration tests for anonymise() (BILTIQ-012).

Real stack, zero mocks: PresidioDetector (Presidio + Indian pack + spaCy NER)
→ Pseudonymiser → generaliser → DPDPRegime → audit chain, all through the
public top-level entry point only.
"""
from __future__ import annotations

import socket

import pytest

from biltiq_privacy import (
    DPDPRegime,
    PresidioDetector,
    anonymise,
    verify_chain,
)

_KEY = b"e2e-test-key-32-bytes-long!!!!!!"
_TS = "2026-06-11T00:00:00+00:00"

# The six IN_* types that survive _merge_detections on the sample blob.
# IN_PHONE and IN_MEDICAL_REG are detected but lose their overlap contests
# under the CDSCO higher-score-wins policy (characterised below): the phone
# span ties UK_NHS @1.0 on (start, score) and the stable sort keeps the
# detector's earlier emission; the medical reg @0.6 is engulfed by a wider
# PERSON span @0.85. Either way the winning span covers the value, so every
# original is still replaced — which is the assertion that matters.
_SURVIVING_INDIAN_TYPES = frozenset(
    {
        "IN_AADHAAR",
        "IN_PAN",
        "IN_ABHA",
        "IN_GSTIN",
        "IN_VOTER_ID",
        "IN_IFSC",
    }
)


@pytest.fixture(scope="module")
def detector() -> PresidioDetector:
    """Module-scoped to amortise the spaCy model load across the three tests."""
    return PresidioDetector()


def test_e2e_indian_pii_full_pipeline(
    detector: PresidioDetector, sample_indian_pii: str
) -> None:
    """AC3 — raw Indian-PII text through the public facade: detected,
    pseudonymised, generalised, DPDP-attested, chain-verified."""
    result = anonymise(
        sample_indian_pii,
        detector=detector,
        key=_KEY,
        generated_at=_TS,
        regime=DPDPRegime(),
    )

    found = {d["entity_type"] for d in result.detections}
    assert _SURVIVING_INDIAN_TYPES <= found, (
        f"missing: {sorted(_SURVIVING_INDIAN_TYPES - found)}"
    )

    # The load-bearing guarantee: every synthetic PII value in the blob is
    # gone from the output — including the phone and medical reg, whose
    # spans were replaced under a different winning label (see note above).
    from tests.fixtures.india import (
        AADHAAR_VALID,
        ABHA_VALID,
        GSTIN_VALID,
        IFSC_VALID,
        MEDICAL_REG_VALID,
        PAN_VALID,
        PHONE_IN_VALID,
        VOTER_ID_VALID,
    )

    for value in (
        AADHAAR_VALID[0],
        ABHA_VALID[0],
        PAN_VALID[0],
        GSTIN_VALID[0],
        VOTER_ID_VALID[0],
        IFSC_VALID[0],
        PHONE_IN_VALID[0],
        MEDICAL_REG_VALID[0],
    ):
        assert value not in result.anonymised_text, value

    assert result.compliance is not None
    statuses = {c.check_id: c.status for c in result.compliance.checks}
    assert result.compliance.total == 8
    # Structurally guaranteed checks (BILTIQ-011 integration precedent) plus
    # DPDP-4: the generalised phone mask carries the "XXXX" marker.
    assert statuses["DPDP-2"] == "pass"
    assert statuses["DPDP-3"] == "pass"
    assert statuses["DPDP-4"] == "pass"
    assert statuses["DPDP-5"] == "pass"

    assert verify_chain([result.audit_row])["valid"] is True


def test_e2e_two_call_chain_verifies(
    detector: PresidioDetector, sample_indian_pii: str
) -> None:
    """AC3 — a second call threads prev_hash; the two-row chain verifies."""
    first = anonymise(
        sample_indian_pii, detector=detector, key=_KEY, generated_at=_TS
    )
    second = anonymise(
        "Follow-up note with no PII.",
        detector=detector,
        key=_KEY,
        generated_at=_TS,
        prev_hash=first.audit_row["hash"],
    )
    report = verify_chain([first.audit_row, second.audit_row])
    assert report["valid"] is True
    assert report["first_broken_index"] is None


def test_e2e_no_network_calls(
    detector: PresidioDetector,
    sample_indian_pii: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4 — the full pipeline runs with socket creation disabled entirely."""
    detector.detect("warm-up")  # build the engine before sockets are blocked

    def _no_sockets(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network socket opened during anonymise()")

    monkeypatch.setattr(socket, "socket", _no_sockets)
    result = anonymise(
        sample_indian_pii,
        detector=detector,
        key=_KEY,
        generated_at=_TS,
        regime=DPDPRegime(),
    )
    assert result.anonymised_text  # pipeline completed offline
