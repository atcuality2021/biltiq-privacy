# SPDX-License-Identifier: MIT
"""Tests for ``biltiq_privacy.core.exceptions``.

Pins the BILTIQ-007 AC4 contract that ``HMACKeyRequiredError`` is importable
from the dedicated ``core.exceptions`` module and is a ``ValueError``
subclass, plus the BILTIQ-009 AC3 contract that ``MissingNERModelError`` is a
distinct ``RuntimeError`` carrying spaCy install guidance.
"""
from __future__ import annotations

from biltiq_privacy.core.exceptions import (
    HMACKeyRequiredError,
    MissingNERModelError,
)


def test_hmac_key_required_is_value_error() -> None:
    """``HMACKeyRequiredError`` subclasses ``ValueError`` (AC4)."""
    assert issubclass(HMACKeyRequiredError, ValueError)


def test_hmac_key_required_is_raisable_and_caught_as_value_error() -> None:
    """An instance carries its message and is catchable as ``ValueError``."""
    try:
        raise HMACKeyRequiredError("key must not be empty")
    except ValueError as exc:  # narrower-than-Exception on purpose
        assert str(exc) == "key must not be empty"
    else:  # pragma: no cover - defensive; the raise above always fires
        raise AssertionError("HMACKeyRequiredError was not raised")


def test_missing_ner_model_error_is_runtime_error() -> None:
    """``MissingNERModelError`` is a distinct ``RuntimeError`` (AC3).

    It is an environment/setup fault, so it must NOT share the
    ``ValueError`` lineage of ``HMACKeyRequiredError`` — a caller catching one
    must not accidentally swallow the other.
    """
    assert issubclass(MissingNERModelError, RuntimeError)
    assert not issubclass(MissingNERModelError, ValueError)
    assert not issubclass(MissingNERModelError, HMACKeyRequiredError)


def test_missing_ner_model_error_message_has_install_guidance() -> None:
    """The message carries the spaCy download command, with and without context (AC3)."""
    # Bare form — the install hint is the whole message.
    assert "spacy download en_core_web_sm" in str(MissingNERModelError())
    # Context form — the prepended context is preserved and the hint appended.
    enriched = MissingNERModelError("en_core_web_sm not found.")
    assert "en_core_web_sm not found." in str(enriched)
    assert "spacy download en_core_web_sm" in str(enriched)
