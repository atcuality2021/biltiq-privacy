# CLAUDE.md — Claude Code Project Instructions

This is a BiltIQ AI repository. Before doing anything in this repo, you must understand the project context, the engineering process, and the rules that govern code in this codebase.

The `biltiq-engineering` plugin is installed and provides the canonical workflow. Skills auto-trigger via the SessionStart hook.

---

## Read order (mandatory before any task)

Read these files in this order before generating, editing, or reviewing any code:

1. **`AGENT_RULES.md`** (repo root) — canonical behavior rules. The 10 anti-patterns, code conventions, banned vocabulary, security rules, **compliance mode**.
2. **`MEMORY.md`** (repo root) — persistent project state. Current focus, recent decisions, known issues, open questions.
3. **`/docs/CONTEXT.md`** — what this product does, who uses it, what we explicitly don't do.
4. **`/docs/GLOSSARY.md`** — project-specific terms. Product names, infrastructure, acronyms.
5. **`/docs/architecture/overview.md`** — system architecture for this repo.
6. **`/docs/architecture/stack.md`** — libraries, wrappers, and utilities available in this repo. Read this before writing any new code (Anti-Pattern #1 defense).
7. **`/docs/architecture/approved-versions.md`** — current vs deprecated APIs (Anti-Pattern #9 defense).

For task-specific work, additionally read:

- `/docs/specs/<task-id>/spec.html`
- `/docs/specs/<task-id>/design.html`
- `/docs/specs/<task-id>/plan.html`

If any of those are missing, **stop and tell the dev** — the task is not ready to start.

---

## How to work in this repo

Use the BiltIQ Attack Loop: **Think → Plan → Build → Review → Test → Ship → Reflect.** The 7 slash commands provided by the `biltiq-engineering` plugin map to these steps:

| Step | Command |
|---|---|
| 1 Think | `/biltiq-engineering:think <task-id>` |
| 2 Plan | `/biltiq-engineering:plan <task-id>` |
| 3 Build | `/biltiq-engineering:build <task-id>` |
| 4 Review | `/biltiq-engineering:review <task-id>` |
| 5 Test | `/biltiq-engineering:test <task-id>` |
| 6 Ship | `/biltiq-engineering:ship <task-id>` |
| 7 Reflect | `/biltiq-engineering:reflect <task-id>` |

Or run the full pipeline by invoking the `attack-loop-orchestrator` skill: tell the agent "let's do BILTIQ-XXX" and it will walk the loop.

For planning, code review, test generation, and doc generation, use the named skills (`plan-reviewer`, `code-reviewer`, `test-generator`, `doc-generator`). They auto-trigger when relevant; you can also invoke explicitly.

---

## What NOT to do in this repo

- **No vibe coding.** Don't generate code without `spec.html`, `design.html`, and `plan.html` present and reviewed.
- **No silent assumptions.** If `spec.html` is ambiguous, ask. Don't guess.
- **No throwaway file residue.** Delete experimental files before committing — no `auth_v2.py`, `auth_new.py`, `*.bak`, `test_scratch_*.py`. CI will fail the PR if these exist.
- **No `any` / `Any` types.** No `# type: ignore` without an inline comment justifying it.
- **No banned vocabulary** in code comments, docs, or commit messages: "cutting-edge", "revolutionary", "empowering", "seamless", "future-ready".
- **No external AI / cloud LLM calls** if this repo's compliance mode in `AGENT_RULES.md` is `on_prem_required`. If `on_prem_preferred`, only with an ADR. If `cloud_ok`, still requires an ADR for any new AI dependency.

---

## Updating MEMORY.md

After significant work in a session, invoke the `memory-curator` skill or update manually:

- New context the next session should know (decisions, gotchas, things in flux).
- Items completed (move from "Current focus" to "Recently completed").
- New open questions.

Don't bloat. Keep under 200 lines. If it grows beyond that, the `memory-curator` skill archives older entries to `/docs/memory-archive/YYYY-MM.md`.

---

## Reporting back to the dev

When you finish a unit of work, summarize:

1. What you did (1-2 sentences).
2. What files changed (list).
3. What tests you generated (count + criterion coverage).
4. Any anti-patterns you avoided (e.g., "I noticed `BaseHTTPClient` already exists in `core/http.py`, so I used it instead of raw `httpx`").
5. Anything you flagged as needing human attention.

Plain reporting only.
