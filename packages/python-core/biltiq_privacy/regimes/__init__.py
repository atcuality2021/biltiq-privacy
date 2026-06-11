# SPDX-License-Identifier: MIT
"""Regulatory regime adapters (DPDP 2023 now; GDPR/HIPAA/CCPA in Phase C).

Re-exports the attestation seam (:class:`Regime`, :class:`ComplianceCheck`,
:class:`ComplianceReport`, :data:`CheckStatus`) and the first regime
(:class:`DPDPRegime`). Importing this package stays light: no Presidio, no
spaCy, no FastAPI (spec AC4) — the residual scan compiles one extra stdlib
regex and reuses the eight BILTIQ-002 patterns by reference.
``EMAIL_PATTERN`` stays module-level in :mod:`biltiq_privacy.regimes.dpdp`
(scan plumbing, not regime surface).
"""
from __future__ import annotations

from biltiq_privacy.regimes.base import (
    CheckStatus,
    ComplianceCheck,
    ComplianceReport,
    Regime,
)
from biltiq_privacy.regimes.dpdp import DPDPRegime

__all__ = [
    "CheckStatus",
    "ComplianceCheck",
    "ComplianceReport",
    "DPDPRegime",
    "Regime",
]
