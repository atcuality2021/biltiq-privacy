# SPDX-License-Identifier: MIT
"""AC1 tests: the ``Regime`` ABC + frozen report dataclasses (BILTIQ-011).

Mirrors ``tests/detectors/test_detectors_base.py``: the seam is pinned
structurally (abstractness, immutability, slots) so a later regime cannot
weaken the contract without a test going red. No mocking — the types under
test are pure stdlib constructs.
"""
from __future__ import annotations

import dataclasses

import pytest

from biltiq_privacy.regimes.base import ComplianceCheck, ComplianceReport, Regime


def _check(status: str = "pass") -> ComplianceCheck:
    """One synthetic check; values are arbitrary non-PII labels."""
    return ComplianceCheck(
        check_id="DPDP-1",
        name="PII Removal Completeness",
        description="All detected PII must be removed or replaced in output",
        status=status,  # type: ignore[arg-type]  # tests pass literal strings; runtime accepts any str
        details="No PII leaked",
        section="Section 8(1) — Data Minimisation",
    )


def _report(passed: int = 8, total: int = 8) -> ComplianceReport:
    return ComplianceReport(
        regime_id="DPDP-2023",
        compliant=passed == total,
        passed=passed,
        total=total,
        checks=(_check(),),
        generated_at="2026-06-11T00:00:00+00:00",
        frameworks=("DPDP Act 2023",),
    )


def test_regime_abc_not_instantiable() -> None:
    """AC1: ``Regime`` is abstract — direct instantiation raises."""
    with pytest.raises(TypeError):
        Regime()  # type: ignore[abstract]  # the error is the assertion


def test_regime_subclass_without_validate_not_instantiable() -> None:
    """AC1: a subclass that omits ``validate`` stays abstract."""

    class Incomplete(Regime):
        regime_id = "X-0000"
        frameworks = ("X",)

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]  # the error is the assertion


def test_regime_minimal_concrete_subclass_returns_report() -> None:
    """AC1: implementing ``validate`` is sufficient to instantiate and run."""

    class Minimal(Regime):
        regime_id = "X-0000"
        frameworks = ("X",)

        def validate(self, original, anonymised, detections, audit_records, *, generated_at):  # type: ignore[no-untyped-def]  # signature typed on the ABC; stub keeps the test focused
            return _report()

    report = Minimal().validate("a", "b", [], [], generated_at="t")
    assert isinstance(report, ComplianceReport)


def test_compliance_check_frozen_and_slotted() -> None:
    """AC1: ``ComplianceCheck`` is immutable and defines no ``__dict__``."""
    check = _check()
    with pytest.raises(dataclasses.FrozenInstanceError):
        check.status = "fail"  # type: ignore[misc]  # the error is the assertion
    assert not hasattr(check, "__dict__")


def test_compliance_report_frozen_and_slotted() -> None:
    """AC1: ``ComplianceReport`` is immutable and defines no ``__dict__``."""
    report = _report()
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.compliant = False  # type: ignore[misc]  # the error is the assertion
    assert not hasattr(report, "__dict__")


def test_compliance_report_score_formats_passed_over_total() -> None:
    """AC2 contract support: ``score`` derives the source's "7/8" form."""
    assert _report(passed=7, total=8).score == "7/8"


def test_identical_reports_compare_equal() -> None:
    """AC2 determinism support: identical field values → equal reports."""
    assert _report() == _report()
