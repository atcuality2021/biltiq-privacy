# SPDX-License-Identifier: MIT
"""Library exceptions for ``biltiq_privacy.core``.

Single home for the exception types named in
``docs/architecture/overview.md`` § Failure modes. ``HMACKeyRequiredError``
lands first (BILTIQ-007), ``MissingNERModelError`` beside it (BILTIQ-009);
the remaining sibling the overview reserves (``BiltiqPrivacyImportError``)
will land here as its owning task ships.
"""
from __future__ import annotations

#: Operator-facing remedy embedded in :class:`MissingNERModelError`. spaCy
#: raises ``OSError`` when ``en_core_web_sm`` is absent; the detector maps it
#: to this guidance so the fix is one copy-paste away (``overview.md`` §
#: Failure modes: "spaCy model missing → MissingNERModelError with install
#: instructions").
SPACY_MODEL_INSTALL_HINT = "python -m spacy download en_core_web_sm"


class HMACKeyRequiredError(ValueError):
    """Raised when a pseudonymisation key is absent or empty.

    Subclasses :class:`ValueError` so consumers already catching value
    errors on misconfiguration are not surprised, while remaining a
    distinct, catchable type. The engine raises this at constructor time —
    before any text is processed — so a missing key fails fast at the
    injection point rather than deep inside a tokenisation loop
    (``overview.md`` failure-mode contract).
    """


class MissingNERModelError(RuntimeError):
    """Raised when the spaCy NER model (``en_core_web_sm``) cannot be loaded.

    Subclasses :class:`RuntimeError`, not :class:`ValueError`: a missing
    model is an environment/setup fault (the package was never downloaded),
    not a bad input value — so it is deliberately distinct from
    :class:`HMACKeyRequiredError`. The Presidio backend raises it lazily, on
    the first ``detect()`` call, by catching the ``OSError`` spaCy emits when
    the model package is absent and re-raising with install guidance
    (``overview.md`` § Failure modes).

    Constructed with no argument, the message is the bare install hint; pass
    a string to prepend context — the hint is appended either way, so the
    remedy is always present.
    """

    def __init__(self, message: str = "") -> None:
        full = f"{message} {SPACY_MODEL_INSTALL_HINT}" if message else SPACY_MODEL_INSTALL_HINT
        super().__init__(full)
