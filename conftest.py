"""Repo-root pytest fixture: anchor rootdir resolution and make ``scripts.*`` importable.

Two roles:

1. **Anchor.** Pytest discovers ``[tool.pytest.ini_options]`` in
   ``/pyproject.toml`` via rootdir resolution. A repo-root ``conftest.py``
   guarantees pytest treats this directory as rootdir for any invocation
   pattern, so the ``pythonpath`` and ``consider_namespace_packages`` settings
   apply consistently to bare ``pytest`` and per-package invocations alike.

2. **Make ``scripts.*`` importable.** ``tests/scripts/test_memory_*.py``
   imports ``scripts._memory_writer`` and ``scripts._memory_curator`` as
   top-level modules. Under ``--import-mode=importlib`` pytest does not insert
   the rootdir into ``sys.path``, so the manual insert below is the contract.
   Removing this line breaks the BILTIQ-003 memory-spine test suite.

The ``packages/<pkg>`` roots needed by both package suites are configured via
``[tool.pytest.ini_options].pythonpath`` in ``/pyproject.toml`` rather than
duplicated here. See ``docs/architecture/stack.md`` § Running tests for the
full test-harness picture.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
