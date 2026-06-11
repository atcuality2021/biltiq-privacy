# SPDX-License-Identifier: MIT
"""Import-purity contract tests for the regimes package — AC4.

spec.html AC4 requires the regimes package to be pure: no FastAPI/DB, and no
Presidio/spaCy load at import time (the residual scan is regex-only). The
probe pattern mirrors ``tests/detectors/test_lazy_import.py`` — a fresh
subprocess isolates ``sys.modules`` from earlier in-process Presidio imports,
and the detectors suite already provides the positive control proving the
harness observes load state.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

_HEAVY_MODULES = ("presidio_analyzer", "spacy", "fastapi")


def _heavy_modules_loaded_by(import_target: str) -> list[str]:
    """Import ``import_target`` in a fresh interpreter; report heavy loads."""
    probe = textwrap.dedent(
        f"""
        import sys
        import {import_target}  # noqa: F401 — the side effect IS the test

        heavy = {_HEAVY_MODULES!r}
        loaded = sorted(
            name for name in heavy
            if any(mod == name or mod.startswith(name + ".") for mod in sys.modules)
        )
        print(f"LOADED={{','.join(loaded)}}")
        """
    ).strip()
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"subprocess import probe failed for {import_target!r}: "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = result.stdout.strip().removeprefix("LOADED=")
    return [name for name in payload.split(",") if name]


def test_importing_regimes_package_loads_no_heavy_frameworks() -> None:
    """AC4: ``import biltiq_privacy.regimes`` loads no Presidio/spaCy/FastAPI."""
    assert _heavy_modules_loaded_by("biltiq_privacy.regimes") == []


def test_importing_dpdp_module_loads_no_heavy_frameworks() -> None:
    """AC4: the DPDP module itself stays regex-only at import time."""
    assert _heavy_modules_loaded_by("biltiq_privacy.regimes.dpdp") == []
