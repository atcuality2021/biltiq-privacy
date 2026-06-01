# SPDX-License-Identifier: MIT
"""Shared pytest fixtures for the python-core test suite.

Home of the ``hmac_key`` fixture reserved in ``docs/architecture/stack.md``
§ Test fixtures. BILTIQ-011 / BILTIQ-012 reuse it for the regime and
end-to-end ``anonymise()`` tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def hmac_key() -> bytes:
    """A deterministic 32-byte key for tests. Never the production key.

    Fixed value so digests are reproducible across runs and processes
    (the determinism the AC3 tests assert). 32 bytes matches the
    HMAC-SHA256 block-aligned key length used in production config.
    """
    return b"biltiq-privacy-test-hmac-key-32b"
