"""Shared fixtures for ``tests/scripts/``.

Every test that touches the memory-spine modules gets a ``tmp_repo`` fixture
that builds an isolated fake repo under ``tmp_path``, with
``BILTIQ_REPO_ROOT`` redirecting the writer/curator away from the real
``.biltiq/``. An autouse safety fixture asserts the env var, if set, stays
inside ``tmp_path`` for the duration of the test.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake repo under tmp_path and redirect writer/curator at it."""
    (tmp_path / ".biltiq").mkdir()
    (tmp_path / "MEMORY.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("BILTIQ_REPO_ROOT", str(tmp_path))
    assert Path(os.environ["BILTIQ_REPO_ROOT"]).resolve() == tmp_path.resolve()
    return tmp_path


@pytest.fixture(autouse=True)
def _no_real_repo_writes(tmp_path: Path) -> Iterator[None]:
    """Belt-and-braces: assert BILTIQ_REPO_ROOT (when set) stays inside tmp_path."""
    yield
    root = os.environ.get("BILTIQ_REPO_ROOT")
    if root is not None:
        resolved = Path(root).resolve()
        assert resolved.is_relative_to(tmp_path.resolve()), (
            f"BILTIQ_REPO_ROOT={root!r} escaped tmp_path={tmp_path!r}; "
            "a test wrote outside the sandbox."
        )
