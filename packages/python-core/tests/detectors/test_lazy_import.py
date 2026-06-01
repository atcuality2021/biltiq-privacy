# SPDX-License-Identifier: MIT
"""Lazy-import contract tests for the detectors package — AC5.

spec.html AC5 requires that importing ``biltiq_privacy.detectors.base`` and
``biltiq_privacy.detectors.presidio_backend`` does **not** transitively load
``presidio_analyzer`` or ``spacy`` into ``sys.modules``. Consumers who only
hold a :class:`~biltiq_privacy.detectors.base.Detector` reference (e.g. the
BILTIQ-012 orchestrator wiring its type) must pay no spaCy / Presidio startup
cost until they actually call :meth:`PresidioDetector.detect`.

Why a subprocess
----------------

``sys.modules`` is process-global. ``test_presidio_backend.py`` imports
Presidio earlier in the same pytest process, so an in-process assertion that
``"presidio_analyzer" not in sys.modules`` would always fail. Each subprocess
gets a fresh interpreter with a fresh ``sys.modules``, isolating the import
boundary cleanly. Mirrors ``tests/indian/test_lazy_import.py``.

Positive control
----------------

A negative test alone is fragile: a module that fails to import anything would
also pass. ``test_probe_positive_control`` exercises the positive case —
importing the recogniser adapter MUST load presidio — proving the harness
genuinely observes module-load state.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_import_probe(import_target: str) -> dict[str, bool]:
    """Run ``import {import_target}`` in a fresh interpreter and report whether
    presidio / spacy ended up in ``sys.modules``.

    Returns ``{"presidio_loaded": bool, "spacy_loaded": bool}``. Raises
    ``AssertionError`` if the subprocess fails, surfacing import errors
    immediately instead of passing vacuously.
    """
    probe = textwrap.dedent(
        f"""
        import sys
        import {import_target}  # noqa: F401 — the side effect IS the test

        presidio_loaded = any(
            mod == "presidio_analyzer" or mod.startswith("presidio_analyzer.")
            for mod in sys.modules
        )
        spacy_loaded = any(
            mod == "spacy" or mod.startswith("spacy.") for mod in sys.modules
        )
        print(f"PRESIDIO_LOADED={{presidio_loaded}}")
        print(f"SPACY_LOADED={{spacy_loaded}}")
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
    parsed = dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines()
    )
    return {
        "presidio_loaded": parsed["PRESIDIO_LOADED"] == "True",
        "spacy_loaded": parsed["SPACY_LOADED"] == "True",
    }


def test_importing_detector_base_does_not_load_presidio() -> None:
    """AC5: importing ``detectors.base`` loads neither presidio nor spaCy.

    The ABC + ``DetectedEntity`` seam imports only the lightweight 007
    ``Detection`` TypedDict; the contract must stay framework-free.
    """
    state = _run_import_probe("biltiq_privacy.detectors.base")
    assert not state["presidio_loaded"], (
        "AC5 violation — importing biltiq_privacy.detectors.base loaded "
        "presidio_analyzer. The detection seam must not import a backend."
    )
    assert not state["spacy_loaded"], (
        "AC5 violation — importing biltiq_privacy.detectors.base loaded spaCy."
    )


def test_importing_presidio_backend_does_not_load_presidio() -> None:
    """AC5: importing ``detectors.presidio_backend`` stays lazy.

    Presidio / spaCy and ``build_engine`` are imported inside ``detect()``,
    not at module scope; the only module-level Presidio reference is the
    ``AnalyzerEngine`` annotation, guarded by ``TYPE_CHECKING``.
    """
    state = _run_import_probe("biltiq_privacy.detectors.presidio_backend")
    assert not state["presidio_loaded"], (
        "AC5 violation — importing biltiq_privacy.detectors.presidio_backend "
        "loaded presidio_analyzer. Check the imports are method-level and the "
        "AnalyzerEngine annotation stays under TYPE_CHECKING."
    )
    assert not state["spacy_loaded"], (
        "AC5 violation — importing biltiq_privacy.detectors.presidio_backend "
        "loaded spaCy."
    )


def test_probe_positive_control() -> None:
    """Harness self-test: importing the recogniser adapter MUST load presidio.

    Without this, a backend module that simply failed to import would make
    the negative tests pass vacuously.
    """
    state = _run_import_probe("biltiq_privacy.indian.recognisers")
    assert state["presidio_loaded"], (
        "harness self-test failed — importing the adapter did not load "
        "presidio_analyzer; the subprocess probe is not observing import "
        "state correctly"
    )
