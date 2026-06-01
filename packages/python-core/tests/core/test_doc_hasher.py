# SPDX-License-Identifier: MIT
"""Tests for ``biltiq_privacy.core.doc_hasher`` (BILTIQ-007 Step 2).

Covers AC1 (SHA-256 / HMAC-SHA256 with key as a parameter, no env read),
AC3 (HMAC determinism + key-sensitivity), and the locked str/bytes-key
equivalence. Golden digests are hardcoded (computed externally) rather
than recomputed with ``hashlib`` in-test, so the assertion is a true
characterization gate and not a circular tautology.
"""
from __future__ import annotations

from pathlib import Path

from biltiq_privacy.core import doc_hasher

# SHA-256("hello") — the canonical well-known digest.
_SHA256_HELLO = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_hash_text_is_sha256_hex() -> None:
    """``hash_text`` returns the known SHA-256 hex digest of the input (AC1)."""
    assert doc_hasher.hash_text("hello") == _SHA256_HELLO


def test_hash_document_bytes() -> None:
    """``hash_document`` hashes raw bytes; ``b"hello"`` == utf-8 ``"hello"`` (AC1)."""
    assert doc_hasher.hash_document(b"hello") == _SHA256_HELLO


def test_hmac_deterministic(hmac_key: bytes) -> None:
    """Same (value, key) yields the same digest across calls (AC3)."""
    first = doc_hasher.hmac_pseudonymise("Rajesh Kumar", key=hmac_key)
    second = doc_hasher.hmac_pseudonymise("Rajesh Kumar", key=hmac_key)
    assert first == second
    # HMAC-SHA256 hex digest is 64 chars.
    assert len(first) == 64


def test_hmac_key_sensitivity(hmac_key: bytes) -> None:
    """A different key yields a different digest for the same value (AC3)."""
    with_key = doc_hasher.hmac_pseudonymise("Rajesh Kumar", key=hmac_key)
    other_key = doc_hasher.hmac_pseudonymise("Rajesh Kumar", key=b"a-different-key")
    assert with_key != other_key


def test_str_and_bytes_key_equivalent() -> None:
    """``"k"`` and ``b"k"`` yield identical output (locked str-convenience)."""
    from_str = doc_hasher.hmac_pseudonymise("value", key="k")
    from_bytes = doc_hasher.hmac_pseudonymise("value", key=b"k")
    assert from_str == from_bytes


def test_no_settings_or_env_import() -> None:
    """Module source reads no ``settings``/env — key is a parameter only (AC1).

    Static source assertion: guards the ``overview.md`` forbidden placement
    (no HMAC key read from env inside python-core) against future refactors.
    """
    source = Path(doc_hasher.__file__).read_text(encoding="utf-8")
    # Tokens that would indicate config/env coupling. Checked as code-ish
    # substrings; the words may appear in prose docstrings, so match the
    # call/attribute forms specifically.
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "import settings" not in source
    assert "from backend" not in source
