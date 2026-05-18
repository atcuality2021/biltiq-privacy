# SPDX-License-Identifier: MIT
"""Lazy-import contract tests — AC5.

spec.html line 168 (AC5) requires that importing
``biltiq_privacy.indian.patterns`` does **not** transitively load
``presidio_analyzer`` or ``spacy`` into ``sys.modules``. The intent is
that consumers who only need pure-regex redaction (e.g. lightweight
log sanitisation) pay no spaCy / Presidio startup cost.

Why a subprocess
----------------

``sys.modules`` is process-global. Any earlier test that imports
``presidio_analyzer`` (e.g. ``test_recognisers.py``) leaves it cached;
an in-process assertion that ``"presidio_analyzer" not in sys.modules``
would always fail under a normal pytest run. Each subprocess gets a
fresh interpreter with a fresh ``sys.modules``, so we can isolate the
import boundary cleanly.

Two-sided assertion
-------------------

A single negative test ("patterns.py does not load presidio") is
fragile: a broken patterns.py module that fails to import anything
would also pass. The companion test
``test_recognisers_import_does_load_presidio`` exercises the positive
case — importing the adapter MUST load presidio — which proves the
subprocess harness genuinely observes module-load state.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_import_probe(import_target: str) -> dict[str, bool]:
    """Run ``import {import_target}`` in a fresh interpreter, then report
    whether presidio / spacy ended up in sys.modules.

    Returns a dict ``{"presidio_loaded": bool, "spacy_loaded": bool}``.
    Raises ``AssertionError`` if the subprocess fails — that surfaces
    import errors immediately instead of silently passing.
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
    stdout = result.stdout.strip().splitlines()
    parsed = dict(line.split("=", 1) for line in stdout)
    return {
        "presidio_loaded": parsed["PRESIDIO_LOADED"] == "True",
        "spacy_loaded": parsed["SPACY_LOADED"] == "True",
    }


def test_patterns_import_does_not_load_presidio() -> None:
    """AC5: ``biltiq_privacy.indian.patterns`` must not pull presidio.

    The pure-regex layer is the lightweight redaction surface; consumers
    who only need ``redact()`` should not pay spaCy / Presidio startup
    cost (~2–4 s + ~200 MB of model memory).
    """
    state = _run_import_probe("biltiq_privacy.indian.patterns")
    assert not state["presidio_loaded"], (
        "AC5 violation — importing biltiq_privacy.indian.patterns "
        "transitively loaded presidio_analyzer. The pure-regex module "
        "MUST not import the Presidio adapter or any module that does."
    )


def test_patterns_import_does_not_load_spacy() -> None:
    """AC5: ``biltiq_privacy.indian.patterns`` must not pull spaCy.

    spaCy is Presidio's default NLP backend; loading it from the
    pure-regex layer would defeat the lazy-import contract even if
    presidio itself were absent.
    """
    state = _run_import_probe("biltiq_privacy.indian.patterns")
    assert not state["spacy_loaded"], (
        "AC5 violation — importing biltiq_privacy.indian.patterns "
        "transitively loaded spaCy. The pure-regex module MUST not "
        "import any NLP backend."
    )


def test_indian_package_import_does_not_load_presidio() -> None:
    """AC5: importing the ``biltiq_privacy.indian`` package alone must
    stay light.

    The ``__init__.py`` for the sub-package is intentionally thin (no
    top-level re-exports of the adapter) — this test guards against a
    future ``__init__`` change that adds ``from .recognisers import …``
    and silently breaks the contract.
    """
    state = _run_import_probe("biltiq_privacy.indian")
    assert not state["presidio_loaded"], (
        "AC5 violation — importing biltiq_privacy.indian transitively "
        "loaded presidio_analyzer. Check that indian/__init__.py does "
        "not import from .recognisers."
    )


def test_recognisers_import_does_load_presidio() -> None:
    """Positive control: importing the adapter MUST load presidio.

    This isn't an AC requirement; it's the harness self-test. Without
    this, a broken patterns.py module that simply fails to import would
    make the negative tests pass vacuously.
    """
    state = _run_import_probe("biltiq_privacy.indian.recognisers")
    assert state["presidio_loaded"], (
        "harness self-test failed — importing the adapter did not load "
        "presidio_analyzer; the subprocess probe is not actually "
        "observing import state correctly"
    )
