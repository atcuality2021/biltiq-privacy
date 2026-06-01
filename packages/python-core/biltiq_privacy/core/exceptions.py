# SPDX-License-Identifier: MIT
"""Library exceptions for ``biltiq_privacy.core``.

Single home for the exception types named in
``docs/architecture/overview.md`` § Failure modes. ``HMACKeyRequiredError``
lands first (BILTIQ-007); the sibling errors the overview reserves
(``BiltiqPrivacyImportError``, ``MissingNERModelError``) will land beside it
as their owning tasks ship.
"""
from __future__ import annotations


class HMACKeyRequiredError(ValueError):
    """Raised when a pseudonymisation key is absent or empty.

    Subclasses :class:`ValueError` so consumers already catching value
    errors on misconfiguration are not surprised, while remaining a
    distinct, catchable type. The engine raises this at constructor time —
    before any text is processed — so a missing key fails fast at the
    injection point rather than deep inside a tokenisation loop
    (``overview.md`` failure-mode contract).
    """
