# SPDX-License-Identifier: MIT
"""Import smoke tests for the biltiq_privacy_server scaffold (BILTIQ-001).

No behavioural / route tests live here — the routes are unimplemented
per docs/specs/BILTIQ-001/spec.html § Out of Scope §5. These tests
verify that the package installs cleanly under hatchling and that the
file:// path reference to biltiq-privacy resolves (proves the cross-
package wiring before Step 4 introduces the workspace).
"""
from __future__ import annotations


def test_import_server() -> None:
    """Top-level server import must succeed with a non-empty __version__."""
    import biltiq_privacy_server

    assert isinstance(biltiq_privacy_server.__version__, str), (
        "biltiq_privacy_server.__version__ must be a str"
    )
    assert biltiq_privacy_server.__version__, (
        "biltiq_privacy_server.__version__ must be non-empty"
    )


def test_can_reach_core() -> None:
    """biltiq_privacy (the library sibling) must be importable from the server venv.

    Verifies that the server's `biltiq-privacy` dep resolved to the
    sibling editable install (since v0.1.0 is not on PyPI). If the server
    installs but the library cannot be imported, the cross-package wiring
    is broken even though the install succeeded.
    """
    import biltiq_privacy

    assert isinstance(biltiq_privacy.__version__, str)
    assert biltiq_privacy.__version__
