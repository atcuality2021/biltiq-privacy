# SPDX-License-Identifier: MIT
"""biltiq-privacy — privacy / anonymisation / compliance engine.

Quick start::

    from biltiq_privacy import DPDPRegime, PresidioDetector, anonymise

    result = anonymise(
        "Call Ravi on 9876543210.",
        detector=PresidioDetector(),
        key=b"your-32-byte-secret-key-here....",
        generated_at="2026-06-11T00:00:00+00:00",  # caller-supplied; no clock read
        regime=DPDPRegime(),
    )
    print(result.anonymised_text, result.compliance.score)

The names re-exported here are the v0.1.0 semver promise. Power-user
surfaces (``Pseudonymiser``, the ``generalise_*`` field functions, the
Indian pattern set, hashing helpers) stay importable from their
subpackages — public but namespaced.

Importing ``biltiq_privacy`` loads neither Presidio, spaCy, nor any
server framework: every heavy import in the chain is method-level
(test-pinned by a subprocess probe).
"""
from __future__ import annotations

from importlib.metadata import version

from biltiq_privacy.core.audit_chain import (
    GENESIS_PREV_HASH,
    ChainedRow,
    VerifyReport,
    verify_chain,
)
from biltiq_privacy.core.exceptions import (
    HMACKeyRequiredError,
    MissingNERModelError,
)
from biltiq_privacy.core.pseudonymiser import AuditRecord
from biltiq_privacy.detectors import DetectedEntity, Detector, PresidioDetector
from biltiq_privacy.pipeline import AnonymiseResult, anonymise
from biltiq_privacy.regimes import (
    CheckStatus,
    ComplianceCheck,
    ComplianceReport,
    DPDPRegime,
    Regime,
)

__version__: str = version("biltiq-privacy")

__all__ = [
    "AnonymiseResult",
    "AuditRecord",
    "ChainedRow",
    "CheckStatus",
    "ComplianceCheck",
    "ComplianceReport",
    "DPDPRegime",
    "DetectedEntity",
    "Detector",
    "GENESIS_PREV_HASH",
    "HMACKeyRequiredError",
    "MissingNERModelError",
    "PresidioDetector",
    "Regime",
    "VerifyReport",
    "__version__",
    "anonymise",
    "verify_chain",
]
