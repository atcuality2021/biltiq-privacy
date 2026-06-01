# SPDX-License-Identifier: MIT
"""Stateless hashing primitives for the privacy engine.

Three pure free functions, ported from the CDSCO-RegAI internal codebase
(``backend/utils/doc_hasher.py``) as a productisation step for the OSS
``biltiq-privacy`` SDK. There is no runtime dependency on CDSCO-RegAI.

The only behavioural change from the original is decoupling from
``settings.HMAC_KEY``: ``hmac_pseudonymise`` takes the key as a
keyword-only argument. The HMAC key is **never** read from the
environment, ``settings``, or any config object inside this package — that
is a forbidden placement per ``docs/architecture/overview.md``. The server
tier resolves the key and injects it (BILTIQ-007 design § Security).

A ``str`` key is utf-8-encoded internally, so passing ``"k"`` and ``b"k"``
yields byte-identical digests — and identical to CDSCO, which always
encoded ``settings.HMAC_KEY`` as utf-8.
"""
from __future__ import annotations

import hashlib
import hmac


def _normalise_key(key: bytes | str) -> bytes:
    """Return ``key`` as bytes, utf-8-encoding a ``str`` (str-convenience)."""
    return key.encode("utf-8") if isinstance(key, str) else key


def hash_document(file_bytes: bytes) -> str:
    """Return the SHA-256 hex digest of raw document bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def hash_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` (utf-8-encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hmac_pseudonymise(value: str, *, key: bytes | str) -> str:
    """Return the HMAC-SHA256 hex digest of ``value`` under ``key``.

    Deterministic: the same ``(value, key)`` yields the same digest across
    processes; a different key yields a different digest. ``key`` is
    keyword-only and accepts ``bytes`` or ``str`` (utf-8-encoded).
    """
    return hmac.new(
        _normalise_key(key),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
