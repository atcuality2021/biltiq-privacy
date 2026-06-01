"""Tests for ``scripts/_retention_writer.py`` — BILTIQ-005.

Local module (no plugin upstream), so these are repo-native tests rather than
a port of a plugin spine suite. ``write_standup`` takes an explicit
``repo_root``, so each test runs against a plain ``tmp_path`` repo with no env
coupling — no ``_hermetic`` fixture needed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts import _retention_writer as rw


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty repo root; docs/standup/ is created by the writer on demand."""
    r = tmp_path / "repo"
    r.mkdir()
    return r


def _write(repo: Path, **overrides: object) -> Path | None:
    kwargs: dict[str, object] = {
        "standup_date": date(2026, 6, 1),
        "yesterday_summary": "vendored memory-spine steps 1-3",
        "today_task": "BILTIQ-006: resume Step 5",
        "branch": "feature/biltiq-006-spine-v1-10-1",
        "blockers": [],
        "repo_root": repo,
    }
    kwargs.update(overrides)
    return rw.write_standup(**kwargs)  # type: ignore[arg-type]


def test_returns_path_under_docs_standup(repo: Path) -> None:
    out = _write(repo)
    assert out == repo / "docs" / "standup" / "2026-06-01.html"
    assert out is not None and out.is_file()


def test_record_contains_branch_and_summaries(repo: Path) -> None:
    out = _write(repo)
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "feature/biltiq-006-spine-v1-10-1" in text
    assert "vendored memory-spine steps 1-3" in text
    assert "BILTIQ-006: resume Step 5" in text
    assert "<title>Standup 2026-06-01</title>" in text


def test_blockers_empty_renders_none(repo: Path) -> None:
    out = _write(repo, blockers=[])
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert '<li class="none">none</li>' in text


def test_blockers_with_mention_rendered(repo: Path) -> None:
    out = _write(
        repo,
        blockers=[{"summary": "vLLM endpoint down", "mention": "@harish"}],
    )
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "vLLM endpoint down" in text
    assert "<code>@harish</code>" in text
    assert '<li class="none">none</li>' not in text


def test_overwrite_is_idempotent(repo: Path) -> None:
    _write(repo, today_task="first version")
    out = _write(repo, today_task="second version")
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "second version" in text
    assert "first version" not in text
    # One date → one file, no .tmp residue from the atomic stage.
    files = sorted(p.name for p in (repo / "docs" / "standup").iterdir())
    assert files == ["2026-06-01.html"]


def test_io_failure_returns_none(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_target: Path, _content: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rw, "_safe_write", _boom)
    assert _write(repo) is None


def test_escapes_user_content_against_injection(repo: Path) -> None:
    """SECURITY: these records are committed HTML opened in a browser, so any
    caller text is an XSS vector. Pin that ``html.escape(quote=True)`` holds for
    every interpolated field — body text, branch name, and blocker mention — so
    a future refactor can't silently drop it.

    quote=True is pinned deliberately: it also escapes ``"`` and ``'``, which
    guards the ``<code>{branch}</code>``/mention interpolations against a future
    move into an attribute context.
    """
    out = _write(
        repo,
        today_task="<script>alert('task')</script>",
        yesterday_summary='<img src=x onerror="alert(1)">',
        branch='feature/"><script>steal()</script>',
        blockers=[{"summary": "<b>bold</b>", "mention": "@x'\"<y>"}],
    )
    assert out is not None
    text = out.read_text(encoding="utf-8")

    # No raw markup or raw quotes from caller content survive into the document.
    assert "<script>" not in text
    assert "<img src=x" not in text
    assert "<b>bold</b>" not in text
    # Escaped forms are present instead.
    assert "&lt;script&gt;alert(&#x27;task&#x27;)&lt;/script&gt;" in text
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text
    # Branch (attribute-adjacent) and mention quotes are escaped too.
    assert "feature/&quot;&gt;&lt;script&gt;steal()&lt;/script&gt;" in text
    assert "@x&#x27;&quot;&lt;y&gt;" in text


# --- write_eod_html: behavior-compatible drop-in for plugin _html_writer ----

_EOD_SECTIONS = {
    "shipped": "PR #5 merged",
    "wip": "BILTIQ-006 step 5",
    "tomorrow": "BILTIQ-006 step 6",
    "blockers": "none",
    "tech_debt_added": "mypy override on spine modules",
    "ai_usage": "26.4M billable tokens",
}


def test_eod_creates_dated_file_in_output_dir(tmp_path: Path) -> None:
    out = rw.write_eod_html(_EOD_SECTIONS, tmp_path)
    assert out == tmp_path / f"{date.today().isoformat()}.html"
    assert out.is_file()


def test_eod_renders_all_section_ids(tmp_path: Path) -> None:
    text = rw.write_eod_html(_EOD_SECTIONS, tmp_path).read_text(encoding="utf-8")
    for sid in ("shipped", "wip", "tomorrow", "blockers", "tech-debt-added",
                "ai-usage", "change-history"):
        assert f'id="{sid}"' in text
    assert "PR #5 merged" in text
    assert "BILTIQ-006 step 5" in text


def test_eod_missing_keys_use_fallbacks(tmp_path: Path) -> None:
    text = rw.write_eod_html({}, tmp_path).read_text(encoding="utf-8")
    # tech_debt_added falls back to "none"; the rest to the em-dash.
    assert ">none</p>" in text
    assert "—" in text


def test_eod_overwrites_same_day(tmp_path: Path) -> None:
    rw.write_eod_html({"shipped": "first"}, tmp_path)
    out = rw.write_eod_html({"shipped": "second"}, tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "second" in text and "first" not in text
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{date.today().isoformat()}.html"]


def test_eod_escapes_content(tmp_path: Path) -> None:
    text = rw.write_eod_html(
        {"shipped": "<script>alert(1)</script>"}, tmp_path
    ).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
