# SPDX-License-Identifier: MIT
"""Shared pytest fixtures for the python-core test suite.

Home of the ``hmac_key`` fixture reserved in ``docs/architecture/stack.md``
§ Test fixtures. BILTIQ-011 / BILTIQ-012 reuse it for the regime and
end-to-end ``anonymise()`` tests.

The detector fixtures (``presidio_engine_indian``, ``sample_indian_pii``,
BILTIQ-009) are defined in ``tests/fixtures/`` and re-exported here by name so
they resolve suite-wide. Re-export — not ``pytest_plugins`` — because
``pytest_plugins`` is only honoured in the rootdir conftest and raises under
pytest 8 when declared in a nested package conftest like this one.
"""
from __future__ import annotations

import pytest

from tests.fixtures.india import sample_indian_pii  # noqa: F401
from tests.fixtures.presidio import presidio_engine_indian  # noqa: F401


@pytest.fixture
def hmac_key() -> bytes:
    """A deterministic 32-byte key for tests. Never the production key.

    Fixed value so digests are reproducible across runs and processes
    (the determinism the AC3 tests assert). 32 bytes matches the
    HMAC-SHA256 block-aligned key length used in production config.
    """
    return b"biltiq-privacy-test-hmac-key-32b"
