# SPDX-License-Identifier: MIT
"""Import + public-surface tests for biltiq_privacy (BILTIQ-001 + BILTIQ-012).

BILTIQ-001 left install/layout smoke tests; BILTIQ-012 adds the v0.1.0
public-API contract: the documented ``__all__`` surface, every name
resolvable, version pin, and the AC4 lazy-import guarantee (importing the
package loads neither Presidio, spaCy, nor FastAPI — pinned by a
subprocess probe, mirroring tests/detectors/test_lazy_import.py).
"""
from __future__ import annotations

import subprocess
import sys

# The v0.1.0 semver promise (spec AC2; design § API Contract). Adding a name
# here is additive; removing or renaming one is a breaking change.
PUBLIC_SURFACE = [
    "AnonymiseResult",
    "AuditRecord",
    "ChainedRow",
    "CheckStatus",
    "ComplianceCheck",
    "ComplianceReport",
    "DPDPRegime",
    "DetectedEntity",
    "Detector",
    "GENESIS_PREV_HASH",
    "HMACKeyRequiredError",
    "MissingNERModelError",
    "PresidioDetector",
    "Regime",
    "VerifyReport",
    "__version__",
    "anonymise",
    "verify_chain",
]


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


def test_public_all_matches_documented_surface() -> None:
    """AC2 — __all__ is exactly the documented 18-name surface, sorted."""
    import biltiq_privacy

    assert list(biltiq_privacy.__all__) == PUBLIC_SURFACE
    assert list(biltiq_privacy.__all__) == sorted(biltiq_privacy.__all__)


def test_every_all_name_importable() -> None:
    """AC2 — every promised name resolves on the package object."""
    import biltiq_privacy

    for name in PUBLIC_SURFACE:
        assert getattr(biltiq_privacy, name) is not None, name


def test_version_is_0_1_0() -> None:
    """AC5 — first publishable release version (requires editable install)."""
    import biltiq_privacy

    assert biltiq_privacy.__version__ == "0.1.0"


def test_top_level_import_loads_no_heavy_deps() -> None:
    """AC4 — `import biltiq_privacy` must not load Presidio/spaCy/FastAPI.

    Subprocess probe so this test cannot be poisoned by modules other tests
    already imported into this interpreter.
    """
    probe = (
        "import sys; import biltiq_privacy; "
        "leaked = [m for m in ('presidio_analyzer', 'presidio_anonymizer', "
        "'spacy', 'fastapi', 'pydantic', 'sqlalchemy') if m in sys.modules]; "
        "sys.exit(repr(leaked) if leaked else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"heavy modules leaked into top-level import: {result.stderr}"
    )
