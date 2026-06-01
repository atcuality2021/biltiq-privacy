# LOCAL-MODULE: created under BILTIQ-005 (no plugin upstream — NOT vendored).
#   Deliberately carries no SYNC-HEADER: the ADR-0004 drift gate pins only the
#   4 vendored spine modules by SHA256. A header here would make the gate diff
#   against a nonexistent upstream. See MEMORY.md § BILTIQ-005.
"""scripts/_retention_writer.py — committed-HTML retention records (BILTIQ-005).

Public API:
    write_standup(*, standup_date, yesterday_summary, today_task, branch,
                  blockers, repo_root=None) -> Path | None
    write_eod_html(sections, output_dir) -> Path

Renders human-readable retention records:
    - ``write_standup`` → ``<repo>/docs/standup/<date>.html`` (typed kwargs),
      the durable companion to the ``standup_post`` memory-spine event: the
      event feeds MEMORY.md, this file is what a human opens later.
    - ``write_eod_html`` → ``<output_dir>/<date>.html``, a behavior-compatible
      drop-in for the plugin's ``_html_writer.write_eod_html`` (v1.10.1). Ported
      so /eod's inline fallback can write a repo-controlled record that doesn't
      drift with ${CLAUDE_PLUGIN_ROOT} across plugin versions. Only the inline
      (non-LLM) writer is ported — the plugin's generate_html/_llm_client path
      is omitted on purpose (it would add an external-AI dep needing an ADR).

Both layouts mirror the existing ``docs/eod/<date>.html`` so the retention
artifacts read consistently.

Contract:
    - Returns the written Path on success.
    - Returns None on I/O failure (logged to stderr); never raises. A standup
      must not crash because docs/ is read-only.
    - All caller-supplied text is HTML-escaped before interpolation.
    - Writes are atomic (stage-to-.tmp then rename) via the inlined _safe_write.
"""

from __future__ import annotations

import html
import os
import sys
from datetime import date as _date
from datetime import datetime, timezone
from pathlib import Path


# Self-contained on purpose: this module ships independently of the memory-spine
# vendoring (BILTIQ-006), so it inlines the two small path helpers it needs
# rather than importing scripts/_paths.py — which only exists once the spine is
# vendored. Behaviour mirrors _paths._resolve_repo_root / _paths._safe_write.
def _resolve_repo_root(repo_root: str | Path | None = None) -> Path:
    """Repo root: explicit arg > CLAUDE_PROJECT_DIR env > cwd."""
    if repo_root is not None:
        return Path(repo_root).resolve()
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def _safe_write(target: Path, content: str) -> None:
    """Atomically write content to target: stage to <target>.tmp then replace.

    On OSError the partial .tmp is cleaned up (best-effort) and the original
    error re-raised, so a failed write never leaves a half-written record.
    """
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass  # best-effort cleanup; the original error is what matters
        raise

# Shared with docs/eod/*.html so both retention artifacts render identically.
_STYLE = """\
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1rem; color: #1f2328; line-height: 1.55; }
  h1 { font-size: 1.5rem; border-bottom: 1px solid #d0d7de; padding-bottom: 0.4rem; }
  h2 { font-size: 1.1rem; margin-top: 1.6rem; color: #24292f; }
  ul { padding-left: 1.3rem; }
  li { margin: 0.2rem 0; }
  code { background: #f6f8fa; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.92em; }
  .meta { color: #6e7781; font-size: 0.85rem; }
  .none { color: #6e7781; font-style: italic; }"""


def _log_warn(msg: str) -> None:
    print(f"[_retention_writer] {msg}", file=sys.stderr)


def _esc(value: str) -> str:
    """HTML-escape a caller string (quote=True covers attribute-unsafe chars)."""
    return html.escape(str(value), quote=True)


def _render_blockers(blockers: list[dict[str, str]]) -> str:
    """Render the Blockers section body as <li> rows.

    Empty list → the italic ``none`` empty-state used across docs/eod. A blocker
    with a ``mention`` appends ``— @who``; the mention is escaped like any other
    caller text so an ``@`` handle can't smuggle markup into the record.
    """
    if not blockers:
        return '    <li class="none">none</li>'
    rows: list[str] = []
    for b in blockers:
        summary = _esc(b.get("summary", ""))
        mention = b.get("mention")
        if mention:
            rows.append(f"    <li>{summary} &mdash; <code>{_esc(mention)}</code></li>")
        else:
            rows.append(f"    <li>{summary}</li>")
    return "\n".join(rows)


def write_standup(
    *,
    standup_date: _date,
    yesterday_summary: str,
    today_task: str,
    branch: str,
    blockers: list[dict[str, str]],
    repo_root: str | Path | None = None,
) -> Path | None:
    """Write the day's standup HTML record. See module docstring for contract."""
    day = standup_date.isoformat()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Standup {day}</title>
<style>
{_STYLE}
</style>
</head>
<body>

<h1>Standup &mdash; {day}</h1>
<p class="meta">Branch: <code>{_esc(branch)}</code> · generated {generated}</p>

<section id="yesterday">
  <h2>Yesterday</h2>
  <ul>
    <li>{_esc(yesterday_summary)}</li>
  </ul>
</section>

<section id="today">
  <h2>Today</h2>
  <ul>
    <li>{_esc(today_task)}</li>
  </ul>
</section>

<section id="blockers">
  <h2>Blockers</h2>
  <ul>
{_render_blockers(blockers)}
  </ul>
</section>

</body>
</html>
"""

    target = _resolve_repo_root(repo_root) / "docs" / "standup" / f"{day}.html"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _safe_write(target, document)
    except OSError as exc:
        _log_warn(f"failed to write standup record to {target}: {exc}")
        return None
    return target


def write_eod_html(sections: dict[str, str], output_dir: str | Path) -> Path:
    """Write the day's EOD HTML to ``<output_dir>/<date>.html``.

    Behavior-compatible drop-in for plugin ``_html_writer.write_eod_html``
    (v1.10.1) — same signature, same section keys, same output. Keys read from
    ``sections`` (missing keys render a fallback):
        shipped, wip, tomorrow, blockers, tech_debt_added, ai_usage

    Atomic via ``_safe_write``; overwrites on same-day re-run. Always uses
    ``date.today()`` (matches the plugin — no date override), so the call site
    stays a pure ``(sections, output_dir)`` contract. Returns the written Path.

    Unlike ``write_standup`` this re-raises on I/O failure rather than returning
    None: it mirrors the plugin contract, where the eod command treats a failed
    record write as a hard error worth surfacing.
    """

    def _e(val: str | None, fallback: str = "—") -> str:
        return html.escape(val or fallback)

    today = _date.today().isoformat()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{today}.html"

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EOD — {today}</title>
  <style>
    :root {{
      --color-border: #e5e7eb; --color-bg: #ffffff;
      --color-bg-subtle: #f9fafb; --color-text: #111827;
      --color-muted: #6b7280; --color-shipped: #16a34a;
      --color-wip: #d97706; --color-blocker: #dc2626;
      --radius: 6px; --max-width: 860px;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif; font-size: 15px;
      line-height: 1.6; color: var(--color-text); background: var(--color-bg);
      padding: 2rem 1rem;
    }}
    main {{ max-width: var(--max-width); margin: 0 auto; }}
    header {{ border-bottom: 2px solid var(--color-border); padding-bottom: 1.25rem; margin-bottom: 2rem; }}
    header h1 {{ font-size: 1.5rem; }}
    section {{ margin-bottom: 2rem; }}
    h2 {{ font-size: 1.1rem; font-weight: 700; border-left: 4px solid var(--color-border); padding-left: 0.75rem; margin-bottom: 0.75rem; }}
    h2.shipped {{ border-color: var(--color-shipped); }}
    h2.wip     {{ border-color: var(--color-wip); }}
    h2.blocker {{ border-color: var(--color-blocker); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 0.5rem 0; }}
    th, td {{ text-align: left; padding: 0.5rem 0.75rem; border: 1px solid var(--color-border); }}
    th {{ background: var(--color-bg-subtle); font-weight: 600; }}
    p {{ margin-bottom: 0.4rem; }}
    @media (max-width: 600px) {{ table {{ font-size: 0.8rem; }} }}
  </style>
</head>
<body>
<main>
  <header><h1>EOD — {today}</h1></header>

  <section id="shipped">
    <h2 class="shipped">Shipped</h2>
    <p>{_e(sections.get('shipped'))}</p>
  </section>

  <section id="wip">
    <h2 class="wip">WIP</h2>
    <p>{_e(sections.get('wip'))}</p>
  </section>

  <section id="tomorrow">
    <h2>Tomorrow</h2>
    <p>{_e(sections.get('tomorrow'))}</p>
  </section>

  <section id="blockers">
    <h2 class="blocker">Blockers</h2>
    <p>{_e(sections.get('blockers'))}</p>
  </section>

  <section id="tech-debt-added">
    <h2>Tech Debt Added</h2>
    <p>{_e(sections.get('tech_debt_added'), 'none')}</p>
  </section>

  <section id="ai-usage">
    <h2>AI Usage</h2>
    <p>{_e(sections.get('ai_usage'))}</p>
  </section>

  <section id="change-history">
    <h2>Change History</h2>
    <table>
      <thead><tr><th>Date</th><th>Section</th><th>What Changed</th><th>Trigger</th></tr></thead>
      <tbody>
        <tr><td>{today}</td><td>all</td><td>Initial draft</td><td>eod</td></tr>
      </tbody>
    </table>
  </section>
</main>
</body>
</html>"""

    _safe_write(out, body)
    return out
