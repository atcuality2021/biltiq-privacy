# ADR 0004: Memory-spine vendoring strategy — fork-and-stay with byte-equivalent sync from plugin

**Status:** proposed
**Date:** 2026-05-29
**Deciders:** @harish (dev), @claude (architect via biltiq-code-architect subagent)
**Related task:** BILTIQ-006
**Related ADRs:** [`docs/adr/0001-memory-spine-pattern.md`](./0001-memory-spine-pattern.md) (BILTIQ-003 — locked the v1 stream-and-projector pattern this ADR re-applies at the v1.10.1 shape)

---

## Context

The repo carries a vendored copy of the memory-spine toolchain — `scripts/_memory_curator.py` + `scripts/_memory_writer.py` — landed by BILTIQ-003 against the schema shape of plugin `biltiq-engineering` v1.6.x. The plugin has since shipped v1.10.1, which owns a different auto-section layout (6 sections via heading-prefix splice, not 3 marker-delimited sections), a different event vocabulary (`task_state_change`, `commit`, `scan_result`, `blocker_open`/`blocker_close`, `decision`, `doctor_install`, plus several more), and enforces per-event JSON-schema validation against `scripts/memory_schemas/`. The plugin's curator fires automatically from `SessionStart` + `PostToolUse` hooks regardless of what the repo vendors. When it runs against the v1.6-shaped `MEMORY.md` it owns whichever headings match its prefix list, wipes the dev-curated content under them, and inserts empty-state placeholders. Symptom-twin: `/biltiq-engineering:standup` emits `standup_post` with `{yesterday_summary, today_task, branch, blockers}` per the v1.10.1 schema while the v1.6 curator reads `{date, doing}` and renders `**Today (?):**` with an empty body. Both symptoms are one root cause: vendored toolchain drift relative to the active plugin.

BILTIQ-006 re-syncs the vendored copy to v1.10.1. This ADR locks the underlying decision — **why we keep vendoring at all** rather than de-vendoring once the plugin is the source of truth — and records the **sync procedure** that keeps vendored and plugin copies aligned over time.

Compliance mode for biltiq-privacy is `on_prem_preferred` (`AGENT_RULES.md` § Compliance). The vendored writer reads this at runtime via `_read_compliance_mode()` and routes accordingly; vendoring an `on_prem_required`-aware writer into an `on_prem_preferred` repo is consistent because the runtime read does not depend on the vendoring source. No external AI / cloud API calls are introduced — the spine is pure-Python deterministic projection plus JSON-schema validation via the `jsonschema` PyPI package, declared as a dev-dependency in root `pyproject.toml` per OQ-D2 resolution (a graceful-degrade `try/except ImportError` shim is retained inside the vendored writer to preserve AC1 byte-equivalence, but is no longer the load-bearing fallback once the dep is declared).

## Decision

**Fork-and-stay vendoring.** Vendor `_memory_curator.py`, `_memory_writer.py`, `_memory_reader.py`, the sibling `_paths.py` import dependency (per amended AC1 + OQ-D3 resolution), and all 14 `memory_schemas/*.json` files the plugin ships (per amended AC2 + OQ-D1 resolution) into `scripts/` at this repo, byte-equivalent to plugin `biltiq-engineering` v1.10.1's `scripts/` tree modulo one permitted divergence: a sync-header comment block prepended to each `.py` file recording the source plugin version, the SHA256 of the source file at sync time, the sync date, and a cross-link to this ADR. The vendored writer's `from jsonschema import Draft7Validator` import is satisfied by declaring `jsonschema >= 4.0` under `[tool.uv].dev-dependencies` in root `pyproject.toml` (per OQ-D2 resolution).

```
# SYNC-HEADER:
#   source: ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_memory_curator.py
#   sha256: <hex>
#   synced: 2026-05-29
#   adr:    docs/adr/0004-memory-spine-vendoring.md
# END-SYNC-HEADER
```

AC1's `diff <(sed '/^# SYNC-HEADER:/,/^# END-SYNC-HEADER/d' scripts/_memory_curator.py) <plugin_curator_path>` validation isolates the header as the only permitted delta; any other change requires an ADR amendment.

The vendored copies are the **source of truth at this repo's commit** — CI uses them, fresh checkouts use them, non-Claude-Code clients use them. The plugin path is treated as a transparent cache for drift verification, not as the runtime source. This is the inverse of how PyPI-style vendoring typically works (which prefers the registry over the vendored copy when both exist); here we prefer the vendored copy because the plugin cache is not durable across machines or CI runners.

JSON schemas under `scripts/memory_schemas/` follow the same byte-equivalence rule but without a sync-header block (JSON does not parse comments). Drift in schemas is detected by full-file diff in `scripts/_check_spine_sync.py`.

## Alternatives considered

1. **De-vendor entirely — rely on the plugin path at `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/<version>/scripts/` for both curator and writer.** Rejected. GitHub Actions runners do not have the Claude Code plugin cache populated; `pytest tests/scripts/` would `ImportError` at collection. Fresh-checkout contributors who haven't installed Claude Code cannot curate `MEMORY.md`. Headless agents and non-Claude tooling cannot resolve the plugin path. The plugin path itself moves between versions and across machines (Linux `~/.claude/plugins/cache/` vs macOS); coupling the repo to it is brittle. Viable only when the plugin ships a pip-installable surface from a public registry — the exit criterion for this ADR.

2. **Pin the plugin to v1.10.x via per-machine Claude Code config.** Rejected. Constraint lives in user-local Claude Code settings, not in the repo; future contributors and CI never see it. Freezes upstream bug fixes and security updates. Cross-cuts other repos — a developer working on biltiq-privacy and biltiq-engineering simultaneously must swap plugin versions per repo. Solves a present-tense problem by introducing a permanent maintenance treadmill.

3. **Fork with local-only modifications — copy v1.10.1, patch the heading-prefix list locally to ignore this repo's `MEMORY.md` shape.** Rejected on Anti-Pattern #2 (Abstraction Bypass). Local modifications fork the upstream contract; every future v1.11 sync becomes a manual merge. The right shape is byte-equivalent vendoring plus a one-shot data migration (BILTIQ-006 AC4 backfill) plus a `MEMORY.md` restructure (AC3) to match what the upstream curator expects.

4. **Submodule the plugin's `scripts/` tree via git submodule.** Rejected. Submodules introduce a new failure mode for contributors who don't run `git submodule update --init`; CI complexity (the submodule URL would point at a not-yet-public internal repo); and submodule pins do not survive a plugin path move. The vendored-copy approach is simpler operationally with the same drift-detection guarantees.

5. **Inline the plugin code into a dedicated package under `packages/` and version it as part of the workspace.** Rejected. Misuses the `packages/` convention — that tier is for public-PyPI-shipped library code (BILTIQ-001 ADR-0001). The memory-spine is dev-tooling, not library surface; it belongs in `scripts/`.

## Consequences

**Positive:**

- CI, fresh checkouts, and non-plugin clients all curate `MEMORY.md` correctly. The repo's spine is independent of the operator's Claude Code state.
- AC1's byte-equivalence + the `_check_spine_sync.py` drift gate make the relationship between vendored and plugin copies legible. The dev can answer "what version of the curator is this repo running?" with a single `head` invocation against the sync-header block.
- Future v1.11 (and beyond) sync is a single mechanical step: rerun `scripts/_check_spine_sync.py --update`, refresh the sync-header, run tests, ship. No merge conflicts because we never fork the upstream behaviour.
- Compliance-mode handling is correct by construction. The runtime read of `AGENT_RULES.md` § Compliance in the vendored writer means the same vendored code does the right thing in any compliance mode without per-repo patching.
- One-time backfill (BILTIQ-006 AC4) ports historical dev-curated content into the v1.10.1 event vocabulary. After the backfill ships, the spine projects cleanly from a single source of events and the dev-curated bullets re-render byte-identically.

**Negative / risks:**

- New dev dependency: `jsonschema >= 4.0` (PyPI, MIT-licensed). The v1.10.1 writer imports `Draft7Validator` from `jsonschema` with a graceful-degrade path (`try: from jsonschema import Draft7Validator; except ImportError: Draft7Validator = None`). When `jsonschema` is absent, `write_event` returns `False` with a stderr warn and **no events are written** — the spine becomes a silent no-op. Mitigated by OQ-D2 resolution: `jsonschema >= 4.0` is declared in root `pyproject.toml` under `[tool.uv].dev-dependencies`, so `uv sync` installs it automatically; the silent no-op path is unreachable in normal install flows. The graceful-degrade shim is retained inside the vendored writer because AC1 demands byte-equivalence, but it is no longer load-bearing. `on_prem_preferred` compliance call: `jsonschema` is a stdlib-style validator, not an AI dependency. Library wheel does not import `scripts/`, so the dep is scoped narrowly to repo tooling (no published-wheel SBOM impact). BILTIQ-006 design § Risks R2 severity downgraded MEDIUM &rarr; LOW.
- `append_estimate_actual` (BILTIQ-022 telemetry surface) lands as additive surface with no consumer in this repo. Cannot be cherry-picked out without violating AC1 byte-equivalence. Accepted as tech debt.
- The plugin's `on_prem_required` PII-strip path (`_strip_external_api_fields`, plugin writer line 163) ships in vendored code but is inert in this `on_prem_preferred` repo. Adds code that never executes here; trade-off accepted to preserve byte-equivalence. The strip path is exercised by `vllm_quality_warning.json` + `routing_payload.json` (both vendored per OQ-D1) which carry `external_api_response: true` annotations on their fields — the path is reachable by tests but dormant in production under this repo's compliance mode.
- Vendor size: ~1289 LOC of Python + **14 JSON schemas** (per OQ-D1 resolution) land under `scripts/`. Increases the repo footprint; minor cost.
- Sync procedure must be honored — every plugin upgrade triggers a re-sync ticket. The 30-day soft-warn + hard-gate-via-followup-1 cadence (Q3 resolution) bounds the drift window.

**Tech debt accepted:**

- No mechanism today auto-detects a plugin version bump and re-syncs. Manual `--force` re-sync via `scripts/install-curator-hook.sh` is the contract (per spec § Out of Scope §3). Future tooling could automate this; out of scope for BILTIQ-006.
- The `_check_spine_sync.py` drift gate runs in `--mode=warn` for 30 days post-merge per Q3 — drift is logged but not blocking during the soft-warn window. BILTIQ-006-followup-1 flips it to hard-gate.
- ~~`_paths.py` is vendored under the same AC1 umbrella but is not named in any AC. Recorded in design.html OQ-D3 as a documentation gap; the spine cannot be vendored without it.~~ <strong>Resolved 2026-05-29:</strong> AC1 amended to enumerate four spine files (`_memory_curator.py`, `_memory_writer.py`, `_memory_reader.py`, `_paths.py`). Spec change-history records the amendment; the gap is closed.

## Sync Procedure

The repo's vendored copies stay aligned with the plugin via `scripts/_check_spine_sync.py`, which runs on every push and after every plugin upgrade.

**On every push (CI gate):**

```
python3 scripts/_check_spine_sync.py --mode=warn
```

Resolves the active plugin scripts dir at `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/<version>/scripts/` (the highest-numbered version dir if multiple exist). For each vendored file (`_memory_curator.py`, `_memory_writer.py`, `_memory_reader.py`, `_paths.py`), diff against the plugin source modulo the sync-header block; for each schema file, full-file diff. Exit codes: `0` no drift (or `--mode=warn` regardless), `1` drift detected, `2` plugin path unresolvable. In `--mode=warn` (the default for 30 days post-merge), prints a structured warning and exits `0` regardless. The hard-gate flip is BILTIQ-006-followup-1.

**On plugin upgrade (manual, dev-driven):**

```
# 1. Verify the active plugin version moved.
ls ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/

# 2. Run the drift check to surface what changed.
python3 scripts/_check_spine_sync.py --mode=strict

# 3. If drift detected and dev decides to re-sync:
python3 scripts/_check_spine_sync.py --update --plugin-version <new-version>

# 4. The --update flag rewrites each vendored file with the new plugin source
#    + a refreshed sync-header block (new SHA256, new sync date). Schemas dir
#    is updated likewise. The sync-header now points at the new version.

# 5. Run the test suite to verify the new vendor.
pytest tests/scripts/

# 6. If green, commit and open a follow-up ticket BILTIQ-<NNN> with the
#    re-sync rationale + the upstream changelog excerpt. Tests must stay
#    green; behavioural changes in the upstream curator surface as test
#    failures, triggering the regular Attack Loop.
```

**SHA256 baseline.** Each `# SYNC-HEADER:` block records the SHA256 of the source plugin file at sync time. Tampering with the upstream plugin path alone is not sufficient to compromise the vendor; the attacker would also need a matching SHA256 commit to this repo (visible in git blame and reviewed at PR time).

**Pre-PR-open snapshot pin.** Per BILTIQ-006 Q2 resolution, the plugin SHA256 is captured at PR-open time and re-verified at Step 6 Ship. If the plugin has moved between PR-open and Ship, an explicit decision lands in the Ship checklist (re-sync to the newer plugin and re-run the affected Build steps, OR ship the older snapshot with a tech-debt note pointing at a follow-up sync ticket).

### SHA256 baseline table

The vendored spine + schemas are pinned at plugin v1.10.1 source SHA256 hashes recorded in this section. Hashes captured at PR-open per BILTIQ-006 Build step 1 (computed by `sha256sum ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/<file>` and `sha256sum ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/memory_schemas/<file>`). The `scripts/_check_spine_sync.py` drift gate (BILTIQ-006 AC8) reads this table at runtime.

**Spine modules (4 files):**

| File | Source path | SHA256 (filled at PR-open) |
|------|-------------|----------------------------|
| `scripts/_memory_curator.py` | `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_memory_curator.py` | `<sha256-hex>` |
| `scripts/_memory_writer.py` | `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_memory_writer.py` | `<sha256-hex>` |
| `scripts/_memory_reader.py` | `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_memory_reader.py` | `<sha256-hex>` |
| `scripts/_paths.py` | `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_paths.py` | `<sha256-hex>` |

**JSON schemas (14 files):**

| File | SHA256 (filled at PR-open) |
|------|----------------------------|
| `scripts/memory_schemas/blocker_close.json` | `<sha256-hex>` |
| `scripts/memory_schemas/blocker_open.json` | `<sha256-hex>` |
| `scripts/memory_schemas/commit.json` | `<sha256-hex>` |
| `scripts/memory_schemas/compliance_flag.json` | `<sha256-hex>` |
| `scripts/memory_schemas/decision.json` | `<sha256-hex>` |
| `scripts/memory_schemas/doctor_install.json` | `<sha256-hex>` |
| `scripts/memory_schemas/eod_post.json` | `<sha256-hex>` |
| `scripts/memory_schemas/estimate_actual.json` | `<sha256-hex>` |
| `scripts/memory_schemas/routing_payload.json` | `<sha256-hex>` |
| `scripts/memory_schemas/scan_result.json` | `<sha256-hex>` |
| `scripts/memory_schemas/security_flag.json` | `<sha256-hex>` |
| `scripts/memory_schemas/standup_post.json` | `<sha256-hex>` |
| `scripts/memory_schemas/task_state_change.json` | `<sha256-hex>` |
| `scripts/memory_schemas/vllm_quality_warning.json` | `<sha256-hex>` |

The `<sha256-hex>` placeholders are replaced with concrete hashes at the start of BILTIQ-006 Build step 1, in the same commit that lands the schemas and the `pyproject.toml` jsonschema dep declaration. Spine module hashes are filled in at the start of each of Build steps 2–5 (one row per step). Filling these in is a pre-commit blocker for the corresponding step; the drift gate has nothing to compare against if any hash remains a placeholder at PR-open.

**Schemas have no sync-header.** JSON does not parse comments, so per-file SHA256 capture is the only drift detection mechanism for the 14 schema files. The `.py` spine files carry both a SHA256 entry here AND the inline `# SYNC-HEADER:` block (belt-and-braces — header is for human inspection at file open; this table is for automated drift gate).

## Exit Criteria

This ADR is amended to `superseded` when **the plugin ships a pip-installable surface from a public registry without the Claude-Code plugin runtime**. Concretely:

1. The plugin author publishes `biltiq-engineering` (or a `biltiq-engineering-spine` subset) to public PyPI.
2. The pip-installable surface exposes `from biltiq_engineering.spine import write_event, read_events, curate` with stable semver and a documented major-version contract.
3. The pip-installable surface is functional **without** the Claude-Code plugin runtime present (i.e. it runs in CI, in a headless agent, in a non-Claude tool).

When all three conditions hold, this repo can de-vendor: delete `scripts/_memory_curator.py` + `_memory_writer.py` + `_memory_reader.py` + `_paths.py` + `memory_schemas/`, add `biltiq-engineering >= X.Y` to `pyproject.toml`, update the slash-command imports, and supersede this ADR with a follow-up that records the migration. The drift gate (`scripts/_check_spine_sync.py`) is deleted in the same PR.

Until then, this ADR stays `accepted` and the sync procedure is the canonical contract.

## How this gets enforced

- `scripts/_check_spine_sync.py` is the runtime gate. Soft-warn for 30 days post-merge per Q3; hard-gate via BILTIQ-006-followup-1.
- `scripts/_check_memory_drift.sh` is the reproduction gate for the underlying bug — verifies the curator produces byte-identical output on consecutive runs (BILTIQ-006 AC8).
- `.github/workflows/biltiq-gates.yml` adds jobs `memory-spine-drift` and `memory-spine-sync` that run both scripts on every push.
- `code-reviewer` skill checks the sync-header block exists on every PR that touches a vendored spine file; absence is treated as an Anti-Pattern #1 / #2 / #9 finding.
- `anti-pattern-scanner` skill runs against `scripts/` on the staged diff; flags any change to vendored content that isn't a sync-header update.
- AGENT_RULES.md § Memory documents the vendoring contract for the agent's read order; future Attack Loop runs see "this is vendored, do not edit" as a project rule.

## What this ADR does NOT cover

- **The runtime semantics of the curator and writer.** Those are owned by the upstream plugin's design documents (`biltiq-engineering`'s `docs/specs/BILTIQ-017a/design.html` per the plugin source's module-docstring breadcrumbs). This ADR records the vendoring decision; the upstream ADR records what the vendored code does.
- **The behavioural contract for new event types or new auto-sections beyond v1.10.1.** When the plugin ships v1.11 with additional renderers or schemas, a follow-up ticket lands here with the sync; this ADR's procedure handles the mechanics.
- **The `MEMORY.md` heading-naming convention.** Owned by the plugin's design.md (the heading prefixes in plugin `_memory_curator.py` line 66 `AUTO_SECTIONS` list are the source of truth). This repo follows.
- ~~**The `jsonschema` dependency declaration.** Recommended path in design.html (add to `scripts/`-tier dev-dependency); final decision at plan.html via OQ-D2.~~ <strong>Resolved 2026-05-29 — now in scope:</strong> `jsonschema >= 4.0` declared under `[tool.uv].dev-dependencies` in root `pyproject.toml` per OQ-D2. Covered by Decision section + Consequences § Negative.
- **Multi-repo `MEMORY.md` consolidation.** Several BiltIQ repos may have their own `MEMORY.md` per-machine. Aggregation (if ever wanted) is out of scope.

## References

- [`docs/specs/BILTIQ-006/spec.html`](../specs/BILTIQ-006/spec.html) — 11 ACs that this ADR's decision satisfies.
- [`docs/specs/BILTIQ-006/design.html`](../specs/BILTIQ-006/design.html) — full design rationale, files-to-touch table, alternatives, risks, per-AC traceability.
- [`docs/adr/0001-memory-spine-pattern.md`](./0001-memory-spine-pattern.md) — BILTIQ-003 ADR that established the per-machine stream + committed projection pattern this ADR re-applies at the v1.10.1 shape.
- [`docs/specs/BILTIQ-003/design.html`](../specs/BILTIQ-003/design.html) — the v1.6 design that BILTIQ-006 supersedes; useful for understanding what changed at the schema layer.
- [`docs/specs/BILTIQ-003/reflect.html`](../specs/BILTIQ-003/reflect.html) line 292 — the 2026-05-18 "curator wipe" investigation that closed as INVALIDATED because the root cause was vendor drift, not the v1.6 curator's empty-stream contract. BILTIQ-006 AC10 amends that entry with a forward-pointer footnote.
- [`AGENT_RULES.md`](../../AGENT_RULES.md) § Compliance line 23 — `on_prem_preferred` mode declaration that the vendored writer reads at runtime via `_read_compliance_mode()`.
- [`AGENT_RULES.md`](../../AGENT_RULES.md) § Memory (lines 113–172) — the v1.6 description that BILTIQ-006 AC9 rewrites to the v1.10.1 shape, with the v1.6 description preserved as a "Historical: BILTIQ-003 v1.6 shape (deprecated 2026-05-29 in BILTIQ-006)" subsection.
- Plugin v1.10.1 source files at `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/` — the vendor source for `_memory_curator.py` (636 LOC), `_memory_writer.py` (425 LOC), `_memory_reader.py` (138 LOC), `_paths.py` (88 LOC), and `memory_schemas/` (14 JSON files).
- Plugin v1.10.1 hook source at `~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/hooks/post-tool-use/hook.sh` lines 75–90 — the auto-fire path that `scripts/install-curator-hook.sh` (BILTIQ-006 AC6) replicates for repo-local invocation.
- BILTIQ-006-followup-1 (placeholder; ticket to be opened at Ship time) — the hard-gate flip for `scripts/_check_spine_sync.py` after the 30-day soft-warn window.

## Change History

| Date | Section | What Changed | Trigger |
|------|---------|--------------|---------|
| 2026-05-29 | all | Initial draft — locks the fork-and-stay vendoring decision over four rejected alternatives (de-vendor, plugin pin, fork-with-mods, submodule, packages-tier inline). Status `proposed`; flipped to `accepted` at BILTIQ-006 Step 6 Ship. Sync Procedure documents the `_check_spine_sync.py` workflow + the PR-open SHA256 pin + the Ship-time re-verify. Exit Criteria names the three concrete conditions for de-vendoring (pip-install + stable semver + Claude-Code-runtime-independence). | BILTIQ-006 Step 2 Plan, design.html § Files to Touch |
| 2026-05-29 | Context / Decision / Consequences (Negative + Tech debt accepted) / What this ADR does NOT cover | OQ-D1 / OQ-D2 / OQ-D3 resolutions propagated. (a) Decision now states all 14 schemas vendor + 4 spine files including `_paths.py`. (b) Context + Consequences § Negative no longer call the `jsonschema` dep "optional" — it is declared as a dev-dep in `pyproject.toml`; R2 severity downgraded LOW. (c) Tech-debt-accepted bullet for `_paths.py` struck through with "resolved by amended AC1" annotation. (d) "What this ADR does NOT cover" bullet for `jsonschema` declaration struck through with "now in scope per OQ-D2" annotation. (e) Consequences § Negative on-prem-strip bullet expanded to name `vllm_quality_warning` + `routing_payload` as the schemas exercising the strip path. (f) Vendor size now lists 14 schemas concretely instead of "7-14 JSON schemas". | BILTIQ-006 Step 2 Plan, design.html Socratic loop iteration 2; dev resolutions confirmed |
| 2026-05-29 | Sync Procedure / new § SHA256 baseline table | Added § SHA256 baseline subsection with two tables (4 spine modules + 14 schemas = 18 rows) carrying `<sha256-hex>` placeholders. Plan.html step 1 / 2 / 3 / 4 / 5 each carry a blocking pre-step requirement to fill in the corresponding row(s) before commit (step 1 fills the 14 schemas; steps 2–5 each fill one spine module). After step 5 commits, `grep -c '<sha256-hex>' docs/adr/0004-memory-spine-vendoring.md` = 0. Provides the concrete baseline that the AC8 drift gate (`scripts/_check_spine_sync.py`, lands at step 8) compares against in CI from step 9 onward. Caught by plan-reviewer as MED finding #5 — "Step 1 schema baseline drift gate is manual". | BILTIQ-006 Step 2 Plan, plan-reviewer verdict-1 MED #5 |
