# MEMORY.md — Project State (Living Document)

**Purpose:** Persistent context for Claude Code (and any AI-IDE) across sessions. The agent reads this on session start and updates it after meaningful work. Prevents every session from starting cold.

**Update rules:**
- Keep under 200 lines. If it grows past that, the `memory-curator` skill archives older entries to `/docs/memory-archive/YYYY-MM.md`.
- Update at end of every meaningful session (`memory-curator` skill).
- Use the structure below. Don't add new top-level sections without an ADR.
- Don't store secrets, credentials, or PII here.

**Last updated:** 2026-05-17 by BILTIQ-001 ship step

---

## Project at a glance

biltiq-privacy is a reusable polyglot privacy/anonymisation/compliance package productised from CDSCO-RegAI. Python engine (framework-free) plus a FastAPI REST sidecar plus thin native SDKs (Node/PHP/Go, v0.1.1+) — one source of truth, polyglot consumption. Layers Indian/EU/US recognisers and DPDP/GDPR/HIPAA/CCPA regime adapters on top of Presidio (depended on, never forked). MIT, public PyPI from v0.1.0 alpha.

**Status:** Pre-implementation. Bootstrap landed (BILTIQ-000) and skeleton merged-or-in-PR (BILTIQ-001 — pyproject + packages/ + dual install paths, PR #1 awaiting reviewer). No engine code yet. Source to port: `/home/atc/Desktop/cdcso/CDSCO-RegAI` (branch `main`).
**Deployment:** Library → public PyPI. Server → native install preferred (`pip install biltiq-privacy-server`), Docker offered (`biltiq/privacy-server:0.1.0`). Both REST endpoints identical.
**Compliance mode:** `on_prem_preferred` — must match `AGENT_RULES.md` § Compliance.
**Primary stakeholders:** @harish — owns CDSCO-RegAI (first consumer), ATC CommandCenter, ManthanQuant.

---

## Current focus (this week)

- **Active sprint:** Pre-implementation — skeleton in PR review, engine port queued.
- **Top 3 tasks in flight:**
  1. BILTIQ-001 — `pyproject.toml` + monorepo `packages/` skeleton — @harish — PR #1 open, 9/9 CI green, awaiting reviewer.
  2. BILTIQ-002 — port `core/pii_patterns.py` from CDSCO-RegAI — not started; blocked on BILTIQ-001 merge.
  3. BILTIQ-003 — port `presidio_engine.py` (Indian recognisers) from CDSCO-RegAI — not started.
- **Top 3 risks:**
  1. CDSCO-RegAI source files have FastAPI/SQLAlchemy/pydantic-settings glue that must be stripped during port. Risk: subtle behaviour change. Mitigation: copy CDSCO-RegAI's 19 unit tests verbatim alongside each port; tests must stay green.
  2. spaCy `en_core_web_sm` bundled adds ~15 MB to wheel. Acceptable v0.1.0; revisit at v0.2.0 if wheel size becomes a complaint.
  3. age binary install path differs by OS. `scripts/install-age.sh` must detect Linux/macOS/Windows; verify on each before v0.1.0 tag.

---

## Recent decisions (last 30 days)

- 2026-05-17 — **ADR-0001:** Dual install paths — pip canonical (`pip install -e packages/python-core -e packages/python-server -e .`) + uv opt-in (`uv sync`). `[project.dependencies]` are plain names, not `file://${PROJECT_ROOT}/...` URLs (uv-only template + pip non-editable install of URL deps make the URL shape unworkable). Both paths first-class; CI uses pip only.
- 2026-05-17 — **ADR-0002:** `en-core-web-sm` 3.7.1 → 3.8.0. Forced by `blis 0.7.11` having no cp313/cp314 wheels; the source build invokes `-mavx512f -mavx512pf -march=knl` and fails on stock runner toolchains. spaCy 3.8.x ships compatible blis with prebuilt wheels.

## Recently completed

- 2026-05-17 — **BILTIQ-001:** pyproject + monorepo `packages/` skeleton (PR #1, 13 commits, 9/9 CI green, awaiting reviewer). 8/8 install combos verified (pip × 4 Python versions + uv × 4 Python versions). Boundary rule enforced via `scripts/check-boundaries.sh`. ADR-0001 + ADR-0002 accepted.
- 2026-05-17 — **BILTIQ-000:** BiltIQ engineering structure bootstrapped — 51 canonical files committed (`adf0b28` + `0edaca5` hotfixes bundled in BILTIQ-001 PR).

---

## Known issues & gotchas

- **CDSCO-RegAI port discipline:** The 10 source files in `SESSION_PROMPT.md` §3 carry framework glue (FastAPI, SQLAlchemy, pydantic-settings, hardcoded vLLM URLs). The library equivalents must take secrets/config as constructor args and return plain dicts/dataclasses. No global settings module.
- **Banned vocabulary:** `cutting-edge`, `revolutionary`, `empowering`, `seamless`, `future-ready` (and the expanded list in `docs/architecture/anti-patterns.md`). Applies to README, regime docs, commit messages, code comments.
- **Indian recognisers (the v0.1.0 differentiator):** Aadhaar, PAN, ABHA, GSTIN, Voter ID, IFSC, phone. Patterns live in CDSCO-RegAI's `presidio_engine.py`. Do not regress accuracy when porting.
- **YAML `#`-after-space comment gotcha:** GitHub Actions workflow `name:` fields containing `Anti-Pattern #N — ...` get truncated by YAML's comment rule to `Anti-Pattern`. Quote any `name:` value containing `#`. Discovered during BILTIQ-001 when `biltiq-gates.yml` was silently failing parse since BILTIQ-000 bootstrap.
- **GitHub Actions workflow validation is branch-scoped:** push events validate workflows against the default branch only. A fix to a broken workflow on a feature branch will not unstick CI until the fix merges to `main`. The 5 `biltiq-gates.yml` jobs in PR #1 are still inert until merge.
- **`${PROJECT_ROOT}` is uv-only:** does not expand under pip; do not use in `[project.dependencies]` if pip must work.
- **`gh pr edit` is broken on `gh < 2.59`** (this machine: 2.46.0, apt-installed, root-owned). The internal GraphQL query touches `repository.pullRequest.projectCards`, which GitHub has deprecated, and the call returns an error. Workaround (no sudo required): use the REST API directly — `gh api --method PATCH /repos/<owner>/<repo>/pulls/<n> --input <(jq -Rs '{body: .}' < body.md)`. System fix is `sudo apt upgrade gh` or installing a newer `gh` to `~/.local/bin/`. Discovered during BILTIQ-001 Step 6 when rewriting PR #1's body.

---

## Open questions

- **Process change (engineering-plugin backlog):** `/biltiq-engineering:build` should require `reflect.html` to be *filled* (not just present) before declaring a task done — or auto-run `/biltiq-engineering:reflect` at end-of-build. Surfaced by BILTIQ-001 Step 4 finding F1.
- **Process change (engineering-plugin backlog):** Build skill should run a "design ↔ diff inventory" check before completion — diff `git diff --name-only` against `design.html`'s files-to-touch list and fail on unexplained deltas. Surfaced by F2.
- **Process change (engineering-plugin backlog):** plan-reviewer (or a pre-commit lint) should flag YAML `name:` fields containing unquoted `#`. Surfaced by the BILTIQ-000 hotfix.
- **Process change (engineering-plugin backlog):** Reviewer slice protocol: per-slice constraint lists should be generated from a `docs/architecture/review-slices.yaml`, not hand-written by the dispatcher. Surfaced by BILTIQ-001 Step 4 5-reviewer dispatch.
- **Process change (engineering-plugin backlog):** Repo bootstrap should pin a minimum `gh` CLI version (≥ 2.59), or BiltIQ skills should replace `gh pr edit` calls with the REST-API form (`gh api PATCH /repos/.../pulls/N`). Surfaced by BILTIQ-001 Step 6 Ship when `gh pr edit` failed on the projectCards GraphQL deprecation. See gotcha in Known issues above.

## Code areas under active change

(none yet — pre-implementation)

---

## Conventions specific to this repo

- Library package: `packages/python-core/biltiq_privacy/` — framework-free, no FastAPI.
- Server package: `packages/python-server/biltiq_privacy_server/` — FastAPI, depends on `biltiq_privacy`.
- Native SDK packages (v0.1.1+): `packages/{node,php,go}/`.
- Regime IDs use legal-section format: `DPDP-1`, `GDPR-Art17`, `HIPAA-§164.514`, `CCPA-§1798.140`.
- HMAC secrets are constructor arguments. No global settings module. No reading from env inside the library — consumers wire env→constructor.
- Pure functions and small classes. Return plain dicts / `@dataclass` objects. No framework-specific return types in library code.

---

## Glossary deltas

(none yet — see `docs/GLOSSARY.md`)

---

## Session log (last 5 sessions)

### 2026-05-17 ~10:00–14:30 IST — BILTIQ-001 Attack Loop (Plan → Reflect ratify)
- Worked on: BILTIQ-001 (pyproject + monorepo skeleton + dual install paths). All 7 Attack-Loop steps complete; PR #1 awaiting human review.
- Did: Spec + design + plan + reflect (`.html`); ADR-0001 (dual install paths) + ADR-0002 (en-core-web-sm 3.8.0). 16 commits on `feature/biltiq-001-pyproject-skeleton`. Step 4 parallel review (5 slices, 27 files) caught 4 doc findings, all fixed in `1711c1b` + `c9b7cc5`. Step 5: 8/8 install combos green, all 10 ACs verified. Step 6: PR #1 opened (9/9 CI green in 55s), CHANGELOG + MEMORY updated (`4eeaede`), PR body rewritten via `gh api PATCH` to match template, gh-tooling gotcha recorded (`62b5ee6`). Step 7: reflect.html extended with the actual Step 5/6/7 timeline + the gh-deprecation as a "we missed" row + a 5th process-change proposal; estimate-actuals JSONL row written to `.biltiq/estimates-history.jsonl` (forward-compat — BILTIQ-022 writer not yet in repo). Bundled BILTIQ-000 hotfix (biltiq-gates.yml `#`-in-name truncation + heredoc extraction).
- Discovered: (a) `[project.dependencies]` with `file://${PROJECT_ROOT}/...` URLs is unworkable under pip — `${PROJECT_ROOT}` is uv-only AND pip installs file-URL deps non-editably. (b) GitHub Actions validates workflows against the default branch, so the `biltiq-gates.yml` hotfix is inert on the feature branch and will only register after merge. (c) YAML's `#`-after-space rule silently truncates unquoted `name:` values. (d) `gh pr edit` is broken on `gh < 2.59` because the internal GraphQL query touches the deprecated `projectCards` field; workaround: `gh api PATCH /repos/.../pulls/<n>`.
- Next session should: Wait for human review on PR #1 → merge → confirm all 5 `biltiq-gates.yml` jobs instantiate post-merge. Then start BILTIQ-002 — port `core/pii_patterns.py` from CDSCO-RegAI into `packages/python-core/biltiq_privacy/`.

### 2026-05-17 ~07:51 IST — claude-onboarding-session
- Worked on: BILTIQ-000 (repo onboarding).
- Did: Ran `/biltiq-engineering:repo-onboarding`. State: fresh. Bootstrapped 51 canonical files. Resolved 10 architectural decisions covering compliance, Python versions, PyPI, versioning, spaCy, monorepo structure (C-as-SDKs), sidecar protocol (REST/FastAPI), fork policy (no fork), deployment (native + Docker), and brief §2 rule 5 FastAPI carve-out.
- Discovered: User's polyglot consumption requirement was not in the brief — surfaced mid-session and resolved with C-as-SDKs + Docker-and-native deployment.
- Next session should: Start BILTIQ-001 — write `pyproject.toml` for `packages/python-core/` and `packages/python-server/`, create the directory skeleton, no implementation yet. _(Done — see BILTIQ-001 session above.)_

---

## Active task

_(no task state recorded yet)_

## Today's activity

_(no activity recorded today)_

## Open blockers

_(no open blockers)_

## Archive

Older entries (>30 days) live in `/docs/memory-archive/YYYY-MM.md`.
