"""Repo-root pytest fixture: make the rootdir importable.

Lets ``tests/scripts/*`` import ``scripts._memory_writer`` as a top-level
module. Pytest does not auto-insert the rootdir into ``sys.path`` because
there is no root-level ``pyproject.toml`` (BILTIQ-001 ships the packages
layout but not a root config); this conftest is the minimal substitute
until consolidated packaging lands.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
