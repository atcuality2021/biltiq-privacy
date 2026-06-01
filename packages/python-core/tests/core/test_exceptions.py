# SPDX-License-Identifier: MIT
"""Tests for ``biltiq_privacy.core.exceptions`` (BILTIQ-007 Step 1).

Pins the AC4 contract that ``HMACKeyRequiredError`` is importable from the
dedicated ``core.exceptions`` module and is a ``ValueError`` subclass, so
consumers catching ``ValueError`` on misconfiguration also catch it.
"""
from __future__ import annotations

from biltiq_privacy.core.exceptions import HMACKeyRequiredError


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
