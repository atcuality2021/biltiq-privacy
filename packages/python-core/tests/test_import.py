# SPDX-License-Identifier: MIT
"""Import smoke tests for the biltiq_privacy scaffold (BILTIQ-001).

No behavioural tests live here — the engine is unimplemented per
docs/specs/BILTIQ-001/spec.html § Out of Scope §9. These tests verify
that the package installs cleanly under hatchling and that __version__
is wired to importlib.metadata. They cover AC1 (layout), AC4 (install
succeeds), and AC8 (subpackages are markers only).
"""
from __future__ import annotations


def test_import_package() -> None:
    """Top-level import must succeed and surface a non-empty __version__."""
    import biltiq_privacy

    assert isinstance(biltiq_privacy.__version__, str), (
        "biltiq_privacy.__version__ must be a str"
    )
    assert biltiq_privacy.__version__, "biltiq_privacy.__version__ must be non-empty"


def test_subpackages_importable() -> None:
    """All five engine subpackages (markers in BILTIQ-001) must import.

    Catches accidental syntax errors in the __init__.py files and verifies
    the layout from docs/architecture/overview.md is in place. AC1 / AC8.
    """
    import biltiq_privacy.backup
    import biltiq_privacy.core
    import biltiq_privacy.detectors
    import biltiq_privacy.recognisers
    import biltiq_privacy.regimes

    # Reference each to keep ruff F401 happy and prove they resolved.
    for module in (
        biltiq_privacy.core,
        biltiq_privacy.recognisers,
        biltiq_privacy.regimes,
        biltiq_privacy.detectors,
        biltiq_privacy.backup,
    ):
        assert module.__name__.startswith("biltiq_privacy."), (
            f"unexpected module name: {module.__name__}"
        )
