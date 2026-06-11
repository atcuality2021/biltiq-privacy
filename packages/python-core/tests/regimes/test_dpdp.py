# SPDX-License-Identifier: MIT
"""AC2/AC3/AC5 tests for the DPDP regime (BILTIQ-011).

Step 2 scope: the residual scan + DPDP-1, including the four documented
behaviour deltas vs CDSCO's ``dpdp_validator.py`` (spec § Open Questions).
Until ``validate()`` is assembled (plan Step 3), DPDP-1 is exercised through
``_check_pii_removal`` directly. All PII is synthetic, sourced from the
BILTIQ-002 ``*_VALID`` fixture tuples — no real identifiers.
"""
from __future__ import annotations

from biltiq_privacy.core.pseudonymiser import AuditRecord, Detection
from biltiq_privacy.regimes.base import ComplianceReport
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


# --- Step 3: the remaining seven checks + validate() assembly ---------------


def _detection(entity_type: str = "IN_AADHAAR") -> Detection:
    return Detection(
        entity_type=entity_type,
        text="<synthetic>",
        start=0,
        end=11,
        score=0.9,
    )


def _audit_record(token: str = "[IN_AADHAAR_1a2b3c4d]") -> AuditRecord:
    return AuditRecord(
        entity_type="IN_AADHAAR",
        pseudonym_token=token,
        position_start=0,
        position_end=11,
        confidence=0.9,
    )


def _statuses(report: object) -> dict[str, str]:
    assert isinstance(report, ComplianceReport)
    return {check.check_id: check.status for check in report.checks}


def _validate(
    *,
    original: str = "Patient Aadhaar 1234.",
    anonymised: str = "Patient Aadhaar [IN_AADHAAR_1a2b3c4d], age XXXX.",
    detections: list[Detection] | None = None,
    audit_records: list[AuditRecord] | None = None,
    regime: DPDPRegime | None = None,
) -> ComplianceReport:
    return (regime or DPDPRegime()).validate(
        original,
        anonymised,
        [_detection()] if detections is None else detections,
        [_audit_record()] if audit_records is None else audit_records,
        generated_at="2026-06-11T00:00:00+00:00",
    )


def test_dpdp2_enough_audit_records_passes() -> None:
    """AC5 (DPDP-2 pass): records ≥ detections attests complete."""
    assert _statuses(_validate())["DPDP-2"] == "pass"


def test_dpdp2_fewer_records_than_detections_warns() -> None:
    """AC5 (DPDP-2 non-pass): fewer records than detections → warning."""
    report = _validate(detections=[_detection(), _detection()], audit_records=[_audit_record()])
    assert _statuses(report)["DPDP-2"] == "warning"


def test_dpdp3_bracketed_token_passes() -> None:
    """AC5 (DPDP-3 pass): a ``[TYPE_hex]`` pseudonym token proves reversibility."""
    assert _statuses(_validate())["DPDP-3"] == "pass"


def test_dpdp3_no_tokens_warns() -> None:
    """AC5 (DPDP-3 non-pass): no bracketed token anywhere → warning."""
    report = _validate(audit_records=[_audit_record(token="redacted")])
    assert _statuses(report)["DPDP-3"] == "warning"


def test_dpdp4_default_marker_present_passes() -> None:
    """AC5 (DPDP-4 pass): a default marker in the output proves generalisation."""
    assert _statuses(_validate(anonymised="Age bracket XXXX recorded."))["DPDP-4"] == "pass"


def test_dpdp4_no_marker_is_info() -> None:
    """AC5 (DPDP-4 non-pass): no marker → info (pseudonymise-only mode)."""
    assert _statuses(_validate(anonymised="token [IN_PAN_9f8e7d6c] only."))["DPDP-4"] == "info"


def test_dpdp4_custom_markers_drive_detection() -> None:
    """AC4 ruling: the injected marker list drives DPDP-4 detection."""
    regime = DPDPRegime(generalisation_markers=("<BRACKET>",))
    report = _validate(anonymised="Generalised to <BRACKET> here.", regime=regime)
    assert _statuses(report)["DPDP-4"] == "pass"


def test_dpdp5_indian_type_detected_passes() -> None:
    """AC5 (DPDP-5 pass): ≥1 ``IN_*`` detection covers the Indian context."""
    assert _statuses(_validate())["DPDP-5"] == "pass"


def test_dpdp5_no_indian_types_warns() -> None:
    """AC5 (DPDP-5 non-pass): only non-Indian entities → warning."""
    report = _validate(detections=[_detection(entity_type="PERSON")])
    assert _statuses(report)["DPDP-5"] == "warning"


def test_dpdp6_always_passes_with_size_metric() -> None:
    """AC5 (DPDP-6, annotated): always-pass in source; details carry the metric."""
    report = _validate(original="aaaaaaaaaa", anonymised="aaaaa")
    check = next(c for c in report.checks if c.check_id == "DPDP-6")
    expected_details = "Text size change: +50.0% (negative means tokens added)"
    assert (check.status, check.details) == ("pass", expected_details)


def test_dpdp6_empty_original_division_guard() -> None:
    """AC5 (DPDP-6 edge): empty original must not divide by zero (source's max())."""
    assert _statuses(_validate(original="", anonymised="x"))["DPDP-6"] == "pass"


def test_ndhm1_with_records_passes_and_empty_warns() -> None:
    """AC5 (NDHM-1 pair): records present → pass; none → warning."""
    assert _statuses(_validate())["NDHM-1"] == "pass"
    assert _statuses(_validate(audit_records=[]))["NDHM-1"] == "warning"


def test_icmr1_always_passes_with_section_metadata() -> None:
    """AC5 (ICMR-1, annotated): always-pass in source; legal section preserved."""
    report = _validate()
    check = next(c for c in report.checks if c.check_id == "ICMR-1")
    assert (check.status, check.section) == ("pass", "ICMR Ethical Guidelines — Chapter 12")


def test_compliant_requires_all_pass() -> None:
    """AC2: one ``warning`` flips ``compliant`` to False (source's passed == total)."""
    report = _validate(audit_records=[])  # DPDP-2/3, NDHM-1 degrade
    assert report.compliant is False and report.passed < report.total


def test_fully_clean_run_is_compliant() -> None:
    """AC2: all eight checks pass → ``compliant`` True, score 8/8."""
    report = _validate()
    assert (report.compliant, report.score) == (True, "8/8")


def test_checks_emitted_in_source_order() -> None:
    """AC2: check order preserved verbatim from the source."""
    expected = ("DPDP-1", "DPDP-2", "DPDP-3", "DPDP-4", "DPDP-5", "DPDP-6", "NDHM-1", "ICMR-1")
    assert tuple(check.check_id for check in _validate().checks) == expected


def test_generated_at_echoed_verbatim() -> None:
    """Dev ruling pin: caller-supplied timestamp is echoed, never replaced."""
    assert _validate().generated_at == "2026-06-11T00:00:00+00:00"


def test_identical_inputs_identical_report() -> None:
    """AC2 determinism: same inputs → equal reports (no clock, no randomness)."""
    assert _validate() == _validate()


# --- Step 4: public surface + pipeline integration ---------------------------


def test_public_names_importable_from_regimes() -> None:
    """Convention: the five regime-surface names re-export from the package."""
    import biltiq_privacy.regimes as regimes

    for name in ("CheckStatus", "ComplianceCheck", "ComplianceReport", "DPDPRegime", "Regime"):
        assert hasattr(regimes, name), f"{name} not importable from biltiq_privacy.regimes"


def test_regimes_all_sorted_and_complete() -> None:
    """Convention: ``__all__`` is sorted and matches the declared surface."""
    import biltiq_privacy.regimes as regimes

    assert regimes.__all__ == sorted(regimes.__all__)
    assert set(regimes.__all__) == {
        "CheckStatus",
        "ComplianceCheck",
        "ComplianceReport",
        "DPDPRegime",
        "Regime",
    }


def test_detector_to_regime_pipeline(sample_indian_pii: str) -> None:
    """Integration: BILTIQ-009 detector → BILTIQ-007 pseudonymiser → regime.

    Proves the design claim that detector output flows into ``validate()``
    unchanged (a ``DetectedEntity`` is a ``Detection`` at runtime). Detections
    are filtered to ``IN_*`` per the documented BILTIQ-002 client-side filter;
    DPDP-1/4 outcomes depend on scan/marker detail, so the assertion targets
    the structurally guaranteed checks.
    """
    from biltiq_privacy.core.pseudonymiser import Pseudonymiser
    from biltiq_privacy.detectors import PresidioDetector

    detections = [
        d for d in PresidioDetector().detect(sample_indian_pii)
        if d["entity_type"].startswith("IN_")
    ]
    anonymised, audit_records = Pseudonymiser(key=b"test-key").pseudonymise_text(
        sample_indian_pii, list(detections)
    )
    report = DPDPRegime().validate(
        sample_indian_pii,
        anonymised,
        detections,
        audit_records,
        generated_at="2026-06-11T00:00:00+00:00",
    )
    statuses = {check.check_id: check.status for check in report.checks}
    assert report.total == 8
    assert (statuses["DPDP-2"], statuses["DPDP-3"], statuses["DPDP-5"]) == (
        "pass",
        "pass",
        "pass",
    )


def test_indian_entity_types_match_recognisers() -> None:
    """Drift guard: the DPDP-5 coverage set equals the recognisers' entities."""
    from biltiq_privacy.indian.recognisers import INDIAN_RECOGNISERS
    from biltiq_privacy.regimes.dpdp import _INDIAN_ENTITY_TYPES

    assert _INDIAN_ENTITY_TYPES == frozenset(
        recogniser.supported_entities[0] for recogniser in INDIAN_RECOGNISERS
    )
