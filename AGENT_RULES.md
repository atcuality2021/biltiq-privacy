# BiltIQ Engineering — AGENT_RULES.md

# Canonical rules for any AI coding IDE (Claude Code default; Cursor, Windsurf, others compatible).
# Drop this in repo root. IDE-specific config files (CLAUDE.md, .cursorrules, .windsurfrules) point to this file.

## Project context

biltiq-privacy is a reusable polyglot privacy/anonymisation/compliance Python package productised from CDSCO-RegAI's battle-tested stack (19/19 unit tests, Presidio integration, audit hash-chain). It exposes DPDP 2023 (India), GDPR (EU), HIPAA (US), and CCPA validators layered on top of Microsoft Presidio's PII detection, plus India/EU/US recognisers, a hash-chain audit primitive, and a pseudonymiser/generaliser pair. MIT-licensed, shipped to public PyPI from v0.1.0 (alpha). Initial consumers: CDSCO-RegAI, ATC CommandCenter, ManthanQuant.

The repo is a **C-as-SDKs monorepo**:
- `packages/python-core/biltiq_privacy/` — the engine. Framework-free. No FastAPI dep.
- `packages/python-server/biltiq_privacy_server/` — FastAPI sidecar exposing REST `/anonymize` and `/validate`.
- `packages/{node,php,go}/` — thin HTTP SDKs that wrap the sidecar (v0.1.1+).

Sidecar deploys **native preferred** (`pip install biltiq-privacy-server` + systemd; ~120 MB RAM) and **Docker offered** (`biltiq/privacy-server:0.1.0`; ~350 MB RAM). Both REST endpoints identical. The library itself has no deploy story — it's a pip-installable dependency.

### Library vs server boundary (critical rule)

`packages/python-core/` MUST NOT import FastAPI, Starlette, uvicorn, or any web framework. Brief §2 rule 5 ("no framework deps in the library") applies here in full. The `biltiq-privacy-server` package is a separate pip distribution that depends on `biltiq-privacy` and adds the FastAPI layer. Code reviewers and CI must block PRs that introduce web-framework imports into `packages/python-core/`.

## Compliance

**Mode:** `on_prem_preferred`

- `on_prem_required` — strict. No external AI / cloud LLM calls in production code paths. Local inference only — vLLM, internal MCP, local embeddings. **Default for healthcare with NHA / DPDP-sensitive workloads, defence (iDEX, ADITI, DRISHTI), government B2G, BFSI with regulated data, or any client contract that mandates data sovereignty.** Auto-block on violation.
- `on_prem_preferred` — external AI calls allowed only with an ADR documenting why local inference doesn't work, what data crosses the boundary, what fallback exists, and what the rollback plan is. An adapter / wrapper module must isolate the cloud call. Default for most BiltIQ products.
- `cloud_ok` — cloud APIs allowed. Any new AI dependency still requires an ADR for cost and lock-in tracking. Default for internal dev tools, prototypes, and deployments where the client has explicitly approved cloud AI in writing.

If this section is missing or unset, agents must default to `on_prem_preferred` and surface the missing declaration.

**Specific external services explicitly allowed for this project:** None as of v0.1.0. The library performs no external AI / cloud calls. The optional `detectors/llm_backend.py` (v0.4.0+) takes an OpenAI-compatible client as a constructor argument — consumers wire their own endpoint; the library itself does not select one. Any future default-on cloud dependency requires an ADR.

## Stack

- Language: Python 3.11, 3.12, 3.13, 3.14 (`requires-python = ">=3.11"`).
- Library framework: **none** (pure functions + small classes; this is library-grade code).
- Server framework: **FastAPI ≥ 0.110** — `packages/python-server/` only.
- ASGI runtime: **uvicorn** — `packages/python-server/` only.
- PII detection engine: **presidio-analyzer ≥ 2.2, < 3**, **presidio-anonymizer ≥ 2.2, < 3** (pinned, vendored for airgap CI, never forked).
- NER model: **spacy + en_core_web_sm** (bundled via pyproject dep).
- Encryption: **age (system binary)** wrapped via subprocess for streaming pipelines (v0.5.0+).
- String distance (if needed): **rapidfuzz** (MIT). **Never python-Levenshtein** (GPL).
- PDF extraction: **not in this repo** — stays in consuming projects to avoid pymupdf's AGPL.
- Build backend: **hatchling** (per-package `pyproject.toml`).
- Lint/format: **ruff** (select `E,F,I,B,UP,DTZ`).
- Type check: **mypy --strict**.
- Test: **pytest** + **pytest-cov** (≥ 90% coverage on `core/` and `recognisers/`).
- CI: GitHub Actions, matrix on Python 3.11 / 3.12 / 3.13 / 3.14.
- Container (optional, sidecar only): **Docker**.

## Working pattern (mandatory)

Every implementation task follows the BiltIQ Attack Loop: **Think → Plan → Build → Review → Test → Ship → Reflect.** When asked to implement a task:

1. **Read first.** Open `/docs/specs/<task-id>/spec.md`, `design.md`, `plan.md`. If any are missing, stop and tell the dev. Read `/docs/architecture/stack.md` to know what wrappers and utilities exist before writing new code.
2. **One step at a time.** Implement the next atomic step from `plan.md`. Don't jump ahead.
3. **Code + tests + docs in same pass.** Generate all three before declaring the step done.
4. **Commit message format:** `<task-id>: <step description>` (e.g., `BILTIQ-002: port pii_patterns.py from CDSCO-RegAI`).
5. **No silent assumptions.** If `spec.md` is ambiguous, ask. Do not guess.
6. **Clean up after yourself.** If you create a test file, throwaway script, or experimental version, delete it before committing — no `*_v2.*`, `*_new.*`, `*_old.*`, `*.bak` files left behind.

## Anti-patterns — these are defects in BiltIQ code

The agent must actively avoid all 10. The dev must scan for them in Review.

The canonical list of the 10 anti-patterns — descriptions, detection signals, and per-language examples (Python, TypeScript / JavaScript, Java, C# / .NET, Go, Rust, C / C++, PHP, Ruby, Solidity) plus a blockchain-specific appendix — lives in **`/docs/architecture/anti-patterns.md`**. That file is the single source of truth; this section is a stub that points there.

Quick reference (full text in canonical):

1. **Duplication** — reuse existing utilities; check `stack.md` first.
2. **Abstraction Bypass** — use the project wrapper, not the raw library.
3. **Error Handling Gaps** — no catch-all handlers that swallow errors; decide explicitly.
4. **Type Safety Violations** — no escape-hatch types; no unjustified type-checker overrides.
5. **Security Anti-Patterns** — parameterized queries, no hardcoded secrets, validate at trust boundaries.
6. **Dead Code / Over-engineering** — build what `spec.md` requires.
7. **Debugging Residue** — no shadow-version files, debug prints, or commented-out code in committed PRs.
8. **Async Misuse** — no blocking I/O on event-loop / coroutine boundaries.
9. **Deprecated API Usage** — check `/docs/architecture/approved-versions.md`.
10. **Fake Test Coverage** — each test asserts one behavior tied to a spec criterion.
11. **HTML/MD boundary violation** — human-facing artifacts (`spec`, `design`, `plan`, `reflect`, reports, EOD summaries) must be `.html` files. Any of these delivered as `.md` under `docs/specs/` is auto-blocked in `code-reviewer` (same severity as #5 and #7). Agent-facing files (`SKILL.md`, `commands/*.md`, `MEMORY.md`, `AGENT_RULES.md`) remain Markdown.

## Code conventions

- **Type hints:** required on all public functions. `from __future__ import annotations` at the top of every module. Strict mode in CI (`mypy --strict`).
- **No bare `Any`.** No `# type: ignore` without a one-line inline justification.
- **Error handling:** all I/O, network, and external calls wrapped with explicit error handling. No bare `except`.
- **Logging:** use `logging` module via `core.log_filter` (the redaction filter from CDSCO-RegAI). No `print()` in production code. Log at appropriate level (DEBUG verbose, INFO state changes, WARNING recoverable, ERROR failures).
- **Secrets:** never in code or config files. Library code takes secrets as constructor arguments (HMAC keys, encryption passphrases). No reading from env inside `packages/python-core/`.
- **PII:** never log PII. If unsure whether a field is PII, treat it as PII. The `log_filter` scrubs `record.msg`, `record.args`, and `extra=` fields.
- **Docstrings:** Google style for Python; JSDoc for JS/TS.

## Banned vocabulary in any output (code comments, docs, commit messages)

The full banned-vocabulary list (with "why" + "say this instead" for each term) lives in **`/docs/architecture/anti-patterns.md` § Banned vocabulary**.

The list is canonical there. Locked terms include "cutting-edge", "revolutionary", "empowering", "seamless", "future-ready" plus an expanded set of consultant-speak and vendor-hype terms. Use plain, specific language — describe what the code does, not how impressive it is.

## Banned in product specs

- Cloud AI models listed as components (GPT-4, Claude Cloud API, Gemini in production paths) — unless the project's compliance mode is `cloud_ok` and an ADR documents the use.
- Unverified compliance claims (SOC 2, ISO 27001, HIPAA, GDPR, FedRAMP).
- Stock-photo style hyperbole.

## Architectural decisions

- Any new dependency requires an ADR before merge.
- Any schema change requires an ADR + migration plan.
- Any new external service integration requires an ADR + threat model note.
- Any cloud AI usage in `on_prem_preferred` mode requires an ADR.
- Any new AI dependency in any mode requires an ADR.
- **Any web-framework import added to `packages/python-core/` requires an ADR explicitly overriding the library/server boundary rule.**

## Memory

The repo carries a per-machine **memory spine** that flows session signal into `MEMORY.md`. Two layers:

- **Stream:** `.biltiq/memory-stream.jsonl` — append-only JSONL, one event per line. Per-machine, gitignored.
- **Projection:** `MEMORY.md` — committed; partly hand-curated, partly regenerated from the stream.

**Public API (writer):**

```python
from scripts._memory_writer import write_event

write_event(
    event_type: str,                 # see vocabulary below
    payload: dict[str, Any],         # JSON-serialisable
) -> None
```

The call is POSIX-atomic (single `os.write()` under `PIPE_BUF`, `O_APPEND`). Encoded line size hard-limited to `PIPE_BUF` (4096 B on Linux) — oversize raises `MemoryEventTooLargeError`. Empty `event_type` or non-dict payload raises `ValueError`. Stream path overridable via `BILTIQ_REPO_ROOT` (test-only).

**v1 event-type vocabulary:**

| `event_type` | Projects to |
|---|---|
| `standup_post` | `auto:current_focus` |
| `blocker_logged` | `auto:current_focus` |
| `commit_metadata` | `auto:code_areas` |
| `reflect_note` | `auto:session_log` |
| `decision_made` | _(counted, not projected in v1)_ |

Producers in v1 are upstream BiltIQ-engineering skills (`/biltiq-engineering:standup` emits `standup_post`; `/biltiq-engineering:reflect` emits `reflect_note` and may emit `decision_made` / `blocker_logged`). `commit_metadata` is reserved in the v1 vocabulary but has no in-repo producer yet — write it explicitly via `write_event(...)` for now.

Unknown event types and events with `schema_version > 1` are counted in `events_seen` but not projected. This is the forward-compat contract — future event types ship as additive writer entries without breaking older curators.

**Projection contract (`MEMORY.md`):**

The curator (`scripts/_memory_curator.py`) reads the stream and splice-replaces content between HTML-comment markers:

- `<!-- auto:<name>:start -->` … `<!-- auto:<name>:end -->` — curator-owned. Names in v1: `current_focus`, `code_areas`, `session_log`. Hand edits to content between these markers are overwritten on the next curator run.
- `<!-- manual:start -->` … `<!-- manual:end -->` — dev-owned. Curator never reads or writes content here.
- Anything outside both marker pairs (the H1, top-level doc framing) is untouched.

If any expected marker is missing, the curator **fails closed**: exits `1`, writes a structured `{"error": "missing_marker", "marker": "..."}` to stderr, leaves `MEMORY.md` byte-equal. This protects hand-curated content from being silently overwritten when the contract drifts.

**Curator CLI:**

```
python3 scripts/_memory_curator.py        # exit 0; emits {"events_seen": N, ...} on stdout
                                          # exit 0 + {"skipped": "..."} if another curator already running (advisory lock)
                                          # exit 1 + {"error": "missing_marker", ...} on contract violation
                                          # exit 2 reserved for unexpected failures
```

Concurrency-safe via `fcntl.flock` on `.biltiq/.curator.lock` (mode `0600`, auto-released on FD close). Two curators racing → second prints `{"skipped": "another curator already running"}` and exits `0`.

**Opt-in post-commit hook:**

The hook at `scripts/hooks/post-commit.sh` spawns the curator in the background (50 ms hard cap on the main thread); it does not emit any event itself. Install with `scripts/install-curator-hook.sh`; uninstall with `--uninstall`. Hook failures are logged to `.biltiq/curator-hook.log` (gitignored) and never block the commit. **Not installed by default** — devs opt in per machine.

**What never lands in the stream:** secrets, PII, raw file contents, payload of any text larger than one screen. The writer is for *session signal* (what task, what blocker, what file touched), not for content snapshots.

## Test rules

- Every public function: at least one unit test (happy path) AND at least one failure-path test.
- Every API endpoint (server package): at least one integration test.
- Tests must run without network or hardware (mock external services).
- Coverage ≥ 90% on `packages/python-core/biltiq_privacy/core/` and `packages/python-core/biltiq_privacy/recognisers/`.
- No more than 50% of dependencies mocked in any single test.
- Server package tests use `TestClient` against the FastAPI app — no real network.

## When asked to generate documentation

- Use the `doc-generator` skill (in plugin `biltiq-engineering`).
- Update CHANGELOG.md, README.md, API docs, and ADRs as applicable in the same pass.
- No marketing language.

## When asked to review a plan

- Use the `plan-reviewer` skill.
- Output verdict: `approved` or `needs revision` with specific issues.

## When asked to review code

- Use the `code-reviewer` skill.
- Check the diff against `design.md` AND the 10 anti-patterns above.
- Auto-block any FastAPI/uvicorn/Starlette import in `packages/python-core/` unless an ADR is referenced in the PR description.
- Output verdict and specific file:line issues.

## When asked to scan for anti-patterns

- Use the `anti-pattern-scanner` skill.
- For large scopes, dispatch the `biltiq-anti-pattern-auditor` subagent in parallel.
