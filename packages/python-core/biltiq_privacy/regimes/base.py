# SPDX-License-Identifier: MIT
"""The attestation abstraction: a ``Regime`` ABC + frozen report dataclasses.

CDSCO-RegAI's ``backend/compliance/dpdp_validator.py`` exposed a single
``validate_dpdp(...) -> dict`` function returning nested plain dicts. This
module lifts only the *shape* of an attestation — any regulatory regime turns
an anonymisation outcome into a report of typed checks — so DPDP now and
GDPR/HIPAA/CCPA (Phase C) slot in behind one seam. There is no runtime
dependency on CDSCO-RegAI, and no Presidio/spaCy/FastAPI import here — the
seam stays framework-free and import-light (spec AC1, AC4).

The report types are ``@dataclass(slots=True, frozen=True)`` per
``approved-versions.md``: an attestation should not be editable after issue,
and value equality lets identical inputs be proven to yield identical reports
(``generated_at`` is caller-supplied; nothing here reads a clock).

A report attests the regime's ported checks against its framework references;
it is not a certification claim.
"""
from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal, TypeAlias

from biltiq_privacy.core.pseudonymiser import AuditRecord, Detection

CheckStatus: TypeAlias = Literal["pass", "fail", "warning", "info"]
"""The four statuses a check can emit, preserved verbatim from the source."""


@dataclass(slots=True, frozen=True)
class ComplianceCheck:
    """One named check's outcome within a :class:`ComplianceReport`.

    ``evidence`` carries ``"TYPE@position"`` locator strings (matched values
    are appended only when the regime was built with ``include_values=True``);
    ``details`` is a human-readable outcome line built from counts, never from
    PII values.
    """

    check_id: str
    """Legal-section ID, e.g. ``"DPDP-1"`` … ``"DPDP-6"``, ``"NDHM-1"``."""

    name: str
    """Short check name, e.g. ``"PII Removal Completeness"``."""

    description: str
    """What the check asserts, preserved verbatim from the source."""

    status: CheckStatus

    details: str
    """Human-readable outcome line (counts and labels, no PII values)."""

    section: str
    """Legal citation, e.g. ``"Section 8(1) — Data Minimisation"``."""

    evidence: tuple[str, ...] = ()
    """Locator strings for non-pass findings; capped by the emitting check."""


@dataclass(slots=True, frozen=True)
class ComplianceReport:
    """A regime's full attestation over one anonymisation outcome.

    ``compliant`` follows the source semantic: every check must be
    ``"pass"`` — ``warning`` and ``info`` count against compliance.
    """

    regime_id: str
    compliant: bool
    passed: int
    total: int
    checks: tuple[ComplianceCheck, ...]
    """All checks in the regime's fixed order."""

    generated_at: str
    """Caller-supplied timestamp, echoed verbatim — no clock read here."""

    frameworks: tuple[str, ...]
    """Framework references the regime attests against (data, not behaviour)."""

    @property
    def score(self) -> str:
        """The source's ``score`` field, derived: ``"7/8"``."""
        return f"{self.passed}/{self.total}"


class Regime(abc.ABC):
    """Strategy interface every regulatory regime implements.

    A regime turns an anonymisation outcome (original text, anonymised text,
    detections, audit records) into a :class:`ComplianceReport`. It holds no
    key, reads no environment, and performs no I/O; configuration is injected
    at construction (see ``DPDPRegime``). Implementations live beside this
    module (``biltiq_privacy.regimes.dpdp`` now; GDPR/HIPAA/CCPA in Phase C).
    """

    regime_id: ClassVar[str]
    """Stable regime identifier, e.g. ``"DPDP-2023"``."""

    frameworks: ClassVar[tuple[str, ...]]
    """Framework references this regime attests against."""

    @abc.abstractmethod
    def validate(
        self,
        original: str,
        anonymised: str,
        detections: Sequence[Detection],
        audit_records: Sequence[AuditRecord],
        *,
        generated_at: str,
    ) -> ComplianceReport:
        """Run every check and assemble the report.

        Args:
            original: The pre-anonymisation text.
            anonymised: The anonymisation output under attestation.
            detections: PII spans found by the detector (a BILTIQ-009
                ``DetectedEntity`` is a ``Detection`` at runtime, so detector
                output flows in unchanged).
            audit_records: One record per replaced span, as produced by the
                BILTIQ-007 pseudonymiser.
            generated_at: Caller-supplied timestamp echoed into the report
                verbatim. The library never reads the clock, so identical
                inputs always produce an identical (``==``-comparable)
                report; consumers wanting wall-clock pass
                ``datetime.now(timezone.utc).isoformat()`` themselves.

        Returns:
            The regime's :class:`ComplianceReport`; non-compliance is
            reported in the return value, never raised.
        """
        raise NotImplementedError
