# SPDX-License-Identifier: MIT
"""AC2/AC3/AC5 tests for the DPDP regime (BILTIQ-011).

Step 2 scope: the residual scan + DPDP-1, including the four documented
behaviour deltas vs CDSCO's ``dpdp_validator.py`` (spec § Open Questions).
Until ``validate()`` is assembled (plan Step 3), DPDP-1 is exercised through
``_check_pii_removal`` directly. All PII is synthetic, sourced from the
BILTIQ-002 ``*_VALID`` fixture tuples — no real identifiers.
"""
from __future__ import annotations

from biltiq_privacy.regimes.dpdp import DPDPRegime, _scan_residual_pii
from tests.fixtures.india import (
    AADHAAR_VALID,
    GSTIN_VALID,
    PHONE_IN_VALID,
)

_SYNTH_EMAIL = "ravi.kumar@example.org"  # synthetic; matches the ported EMAIL pattern


def test_dpdp1_clean_text_passes() -> None:
    """AC5 (DPDP-1 pass): output with no PII shape attests clean."""
    check = DPDPRegime()._check_pii_removal("Patient presented with fever. Plan: rest.")
    assert (check.status, check.details) == ("pass", "No PII leaked")


def test_dpdp1_residual_aadhaar_fails() -> None:
    """AC5 (DPDP-1 fail): a leaked Aadhaar fails the check."""
    check = DPDPRegime()._check_pii_removal(f"ID on file: {AADHAAR_VALID[0]}.")
    assert check.status == "fail"


def test_dpdp1_residual_email_fails() -> None:
    """AC3: the ported EMAIL pattern (absent from BILTIQ-002) catches leaks."""
    check = DPDPRegime()._check_pii_removal(f"Reach me at {_SYNTH_EMAIL} anytime.")
    assert check.status == "fail"


def test_dpdp1_residual_gstin_fails_stricter_than_source() -> None:
    """Delta (a) pin: source scanned 5 types; a leaked GSTIN now fails DPDP-1."""
    check = DPDPRegime()._check_pii_removal(f"Vendor GSTIN {GSTIN_VALID[0]} on invoice.")
    assert check.status == "fail"


def test_phone_underscore_boundary_delta() -> None:
    """Delta (b) pin: ``\\b`` lets an underscore-glued phone go unmatched.

    The source's lookbehind ``(?<![a-zA-Z0-9])`` flagged ``patient_<phone>``
    filenames; BILTIQ-002's ``\\b`` treats the underscore as a word character,
    so no boundary exists and the match is suppressed — and the scan's own
    underscore heuristic would skip it anyway. Documented, dev-ruled.
    """
    bare_phone = PHONE_IN_VALID[0].replace("+91", "").replace("-", "").replace(" ", "")
    check = DPDPRegime()._check_pii_removal(f"see patient_{bare_phone}.pdf")
    assert check.status == "pass"


def test_pseudonym_tokens_not_flagged() -> None:
    """AC2: both token-skip heuristics keep ``[TYPE_hex]`` tokens out of the scan."""
    text = "Aadhaar [IN_AADHAAR_1a2b3c4d] and phone [IN_PHONE_9f8e7d6c] replaced."
    assert _scan_residual_pii(text) == []


def test_evidence_locators_only_by_default() -> None:
    """Delta (c) pin: default evidence is ``TYPE@position`` — no matched text."""
    leaked = AADHAAR_VALID[0]
    check = DPDPRegime()._check_pii_removal(f"ID {leaked}.")
    assert all(leaked not in item for item in check.evidence) and check.evidence


def test_include_values_true_appends_value() -> None:
    """Dev ruling pin: ``include_values=True`` opts in to value-carrying evidence."""
    leaked = AADHAAR_VALID[0]
    check = DPDPRegime(include_values=True)._check_pii_removal(f"ID {leaked}.")
    assert any(item.endswith(f":{leaked}") for item in check.evidence)


def test_masked_values_filtered_via_markers() -> None:
    """AC2: the default markers skip XXXX-containing values (source's filter).

    The value must actually match a residual pattern for the filter to be
    exercised — an email is the only residual type whose text can contain a
    marker substring (the ID patterns are digit-shaped).
    """
    check = DPDPRegime()._check_pii_removal("Contact ravi.XXXX@example.org soon.")
    assert check.status == "pass"


def test_custom_markers_drive_dpdp1_filter() -> None:
    """Design-review ruling pin: an overridden marker list changes DPDP-1.

    With markers that match nothing in the text, the XXXX-containing email
    above is no longer filtered — the same residual now fails the check.
    """
    check = DPDPRegime(generalisation_markers=("<MASKED>",))._check_pii_removal(
        "Contact ravi.XXXX@example.org soon."
    )
    assert check.status == "fail"


def test_descriptive_marker_masks_residual_delta() -> None:
    """Delta (d) pin: a default descriptive marker can mask a real leak.

    ``"India"`` (a default marker) appears inside the leaked email below, so
    the default config filters it — where CDSCO's XXXX-only filter would
    flag it. ``generalisation_markers=("XXXX",)`` restores source-strict
    behaviour. Dev-ruled trade-off; this test keeps it visible.
    """
    text = "Escalate to contact@AirIndia.com please."
    assert DPDPRegime()._check_pii_removal(text).status == "pass"
    assert DPDPRegime(generalisation_markers=("XXXX",))._check_pii_removal(text).status == "fail"


def test_evidence_capped_at_five() -> None:
    """AC2: six residuals → 5 evidence entries, full count in ``details``."""
    text = " | ".join(f"mail{i}@example{i}.org" for i in range(6))
    check = DPDPRegime()._check_pii_removal(text)
    assert (len(check.evidence), check.details) == (5, "6 residual PII found")
