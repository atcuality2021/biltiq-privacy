# ADR 0001: Dual contributor install paths — pip canonical, uv opt-in

**Status:** accepted
**Date:** 2026-05-17
**Deciders:** @harish (dev), @claude (architect via biltiq-code-architect subagent)
**Related task:** BILTIQ-001

## Context

The biltiq-privacy repo is a monorepo with two Python distributions under `packages/`: `biltiq-privacy` (the library, `packages/python-core/`) and `biltiq-privacy-server` (the FastAPI sidecar, `packages/python-server/`). AC10 of BILTIQ-001 requires that a first-time contributor can run a single command at the repo root and end up with both packages installed editably, with the server resolving the library from the local sibling source tree (not from PyPI — v0.1.0 is not yet published).

Two contributor populations are in scope. Internal BiltIQ engineers default to standard pip workflows. External OSS contributors arrive with whatever Python toolchain they already use. Forcing a second toolchain install (e.g., uv) on either group would raise the floor for first-PR contribution, which conflicts with the MIT-license / public-PyPI posture documented in [MEMORY.md](../../MEMORY.md) and BILTIQ-000 decision §6 (C-as-SDKs monorepo).

CI separately needs a deterministic install path that works on GitHub-hosted runners across Python 3.11/3.12/3.13/3.14 without depending on a uv-managed cache.

## Decision

The repo root `pyproject.toml` is a real installable hatchling-built metapackage named `biltiq-privacy-workspace`, version `0.1.0`, classified `Private :: Do Not Upload` (PyPI safety guard). Its `[project.dependencies]` are **plain names** — `biltiq-privacy` and `biltiq-privacy-server` — not `file://` URL references.

The canonical pip command is:

```bash
pip install -e packages/python-core -e packages/python-server -e .
```

Three editable targets in one shell command. pip resolves the sibling packages from the local checkouts on disk because they are installed first; the root metapackage then finds them already-present and the `[project.dependencies]` entries resolve to the editable installs. AC10's "contributor onboarding works without a second toolchain" intent is satisfied. CI uses this path exclusively. No second toolchain on runners.

The same `pyproject.toml` additionally carries a `[tool.uv.workspace]` declaration listing both packages as workspace members, plus `[tool.uv.sources] { workspace = true }` so uv resolves the same plain dependency names to the local workspace members instead of reaching for PyPI (where v0.1.0 is not yet published). Contributors who prefer uv (faster, lockfile-aware, ~60s warm vs pip's ~90s) get the equivalent setup via `uv sync`. uv is documented as an opt-in developer tool, not pinned in either distribution's runtime deps, and not invoked by CI.

**Why plain names instead of `file://${PROJECT_ROOT}/...` URLs** (the original Step-1 design): two issues surfaced during Step 4 verification. (a) `${PROJECT_ROOT}` is a uv-only template variable — pip does not expand it, so the literal URL form was unresolvable under pip. (b) pip installs `[project.dependencies]` entries non-editably even when written as `file:` URLs, so `pip install -e .` alone would not produce an editable dev tree. Plain names + pre-installed editable siblings is the only shape that delivers AC10 + a fully editable dev tree under pip. The shift is recorded in `docs/specs/BILTIQ-001/design.html` change-history (Step 3 + Step 4 rows).

Both install paths are first-class supported. The 8-combo gate at plan Step 4 (4 Python versions × 2 install paths) verifies equivalence before merge.

Each package's own `pyproject.toml` (`packages/python-core/pyproject.toml`, `packages/python-server/pyproject.toml`) remains the sole source of truth for that package's PyPI metadata. Downstream consumers continue to see two clean, independently-versioned distributions; the root metapackage is invisible outside the repo.

## Alternatives considered

1. **uv-workspaces only — uv is the sole supported install path.** Rejected by @harish on 2026-05-17. Mandates uv as a contributor dependency. Faster and cleaner internally, but raises the floor for external OSS contributors who do not already run uv. Subagent's initial recommendation; overridden.

2. **Hatch native workspaces (`[tool.hatch.envs.*]` across packages).** Rejected. Hatch's multi-package environment feature is built around shared environments for a single project, not cross-package editable installs with workspace path resolution. Getting `biltiq-privacy-server` to pick up an editable `biltiq-privacy` sibling requires custom scripts and is brittle on first-time-contributor setup. Fails the AC10 "one command" smell test.

3. **Poetry workspaces (path deps + `[tool.poetry.group]`).** Rejected. Forces Poetry as the project's lockfile / install tool, which conflicts with the published-via-hatch-build-backend posture (BILTIQ-000 decision §6 implies one build backend) and adds a heavyweight dependency most consumers will not need. Two orchestration tools (poetry + hatch) is needless surface area.

4. **No workspace — each package independent, contributors run `pip install -e` twice.** Rejected. Works correctly but fails AC10 ("one command at repo root"). Also makes the server's dependency on the local core fragile: `pip install -e packages/python-server` resolves `biltiq-privacy` from PyPI by default, which does not exist at v0.1.0, causing confusing errors for first-time contributors.

## Consequences

**Positive:**
- AC10 satisfied without forcing uv on any contributor. Both `pip install -e packages/python-core -e packages/python-server -e .` (pip canonical) and `uv sync` (uv opt-in) produce the same editable install of both packages from a single shell command at the repo root.
- CI runs only the pip path on stock GitHub runners — no uv install step, no extra cache layer.
- Each published package keeps its own clean `pyproject.toml`; downstream consumers see two normal PyPI distributions, not a workspace artifact.
- uv contributors get the faster install path (~30% wall-clock reduction on warm cache per [§ Performance Considerations](../specs/BILTIQ-001/design.html)) without the project taking on a uv-only commitment.

**Negative / risks:**
- Two install paths to keep in sync. Drift (e.g., a dep added to `[project.dependencies]` but not reflected in `[tool.uv.sources]`) would cause one toolchain to install a stale version while the other uses the local checkout. Mitigated by the plan Step 4 8-combo gate and a side-by-side review of both blocks in the BILTIQ-001 PR description.
- Adds one TOML file (`pyproject.toml` at repo root) of ongoing maintenance, with two path-dep entries that must match the package names in `packages/*/pyproject.toml`.
- Surface area increase if a future contributor invokes a tool that reads only `[project.dependencies]` or only `[tool.uv.workspace]` and not both. The 8-combo gate catches this on PR; long-term mitigation is the side-by-side PR review note.

**Tech debt accepted:**
- The pip canonical command requires the contributor to name three editable targets in one line (`packages/python-core`, `packages/python-server`, `.`). Less ergonomic than the originally-planned single-target `pip install -e .`, but the only shape that delivers a fully editable dev tree under pip without forcing `[tool.hatch.metadata.allow-direct-references]` + URL deps (which break under pip and need a uv-only template variable). Documented in `README.md` § Quick start and the root `pyproject.toml` header.

## References

- [`docs/specs/BILTIQ-001/spec.html`](../specs/BILTIQ-001/spec.html) — AC10 ("Running `pip install -e packages/python-core -e packages/python-server -e .` at the repo root installs both packages editably in one shell command. The equivalent uv path is `uv sync`. Both paths are first-class.").
- [`docs/specs/BILTIQ-001/design.html`](../specs/BILTIQ-001/design.html) § Approach + Alternatives + ADRs Needed.
- [`docs/architecture/approved-versions.md`](../architecture/approved-versions.md) § Hard dependency pins.
- [`docs/architecture/overview.md`](../architecture/overview.md) § Monorepo layout.
- BILTIQ-000 decision §6 (C-as-SDKs monorepo). See [MEMORY.md](../../MEMORY.md).
- 2026-05-17 dev-architect conversation locking the dual-path decision over the subagent's initial uv-only recommendation.

## Change History

| Date | Section | What Changed | Trigger |
|------|---------|--------------|---------|
| 2026-05-17 | all | Initial draft — dual install paths decision, 4 alternatives rejected, consequences, accepted tech debt. | BILTIQ-001 Step 1 |
| 2026-05-17 | Decision, Consequences | Install-shape paragraphs revised to match implementation reality. Original draft described `[project.dependencies]` as `file://${PROJECT_ROOT}/...` URL refs enabled by `[tool.hatch.metadata.allow-direct-references]`; Step 3 + Step 4 verification revealed this shape is unworkable (`${PROJECT_ROOT}` is uv-only; pip installs `[project.dependencies]` non-editably even with file URLs). Replaced with the plain-name + pre-installed-siblings shape that ships in `pyproject.toml`. Decision intent unchanged; only the mechanism was corrected. Caught at BILTIQ-001 Step 4 (Review) slice C suggestion + slice E finding F4. | BILTIQ-001 Step 4 review |
