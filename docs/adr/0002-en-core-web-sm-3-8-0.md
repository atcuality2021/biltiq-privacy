# ADR 0002: Bump en-core-web-sm 3.7.1 → 3.8.0 for Python 3.13/3.14 wheel availability

**Status:** accepted
**Date:** 2026-05-17
**Deciders:** @harish (dev), @claude (architect)
**Related task:** BILTIQ-001 (Step 2 verification)

## Context

During BILTIQ-001 Step 2 verification, `pip install -e packages/python-core` failed on Python 3.13 at the `blis` build stage. `blis 0.7.11` has no `cp313` or `cp314` wheel on PyPI; attempting a source build invokes gcc with `-mavx512f -mavx512pf -march=knl` flags and fails on the runner's default toolchain. Per plan.html Risk #1, this is the named escalation case ("if the source build fails on a binary dep `blis`, escalate to dev").

Tracing the dependency chain, the forcing function is the `en-core-web-sm` URL pin (set in BILTIQ-000 as `3.7.1`):

```
en-core-web-sm 3.7.1     (URL pin in approved-versions.md)
  └─ spacy 3.7.x         (model compatibility constraint)
       └─ thinc 8.2.x    (spacy 3.7 hard-pin)
            └─ blis <0.8.0,>=0.7.8   (thinc 8.2 hard-pin → only blis 0.7.x matches)
                 └─ no cp313/cp314 wheels   ← failure
```

`en-core-web-sm 3.8.0` was released 2024-09-30 and is the next available release for this model. spaCy `3.8.x` (released alongside) uses `thinc 8.3.x` which allows `blis >=1.0`. `blis 1.3.x` ships pre-built wheels for cp312 / cp313 / cp314. Adopting the model bump removes the source-build path on 3.13 and 3.14 entirely; both install in seconds instead of failing or running gcc.

The library exposes no spaCy 3.7-specific surface today (BILTIQ-001 is pre-implementation; recogniser code lands in BILTIQ-002+). Switching the NER model from 3.7.1 to 3.8.0 has no API impact at this scaffolding stage. Future recogniser code will write against the spaCy 3.x API surface that is stable across both minors.

## Decision

The `en-core-web-sm` pin in `approved-versions.md § Hard dependency pins` and in `packages/python-core/pyproject.toml` moves from `3.7.1` to `3.8.0`. The URL is the exact GitHub Releases asset URL for `en_core_web_sm-3.8.0.tar.gz` from the `explosion/spacy-models` repository. The pin remains a URL ref (not a PyPI index name) because Explosion does not publish these models to PyPI; this preserves the `[tool.hatch.metadata.allow-direct-references]` posture from [ADR-0001](0001-dual-install-paths.md).

Indirect resolution consequences (no pyproject changes needed beyond the URL):

- `spacy` resolves to `3.8.x` (still within the `>=3.7,<4` band documented in approved-versions).
- `thinc` resolves to `8.3.x`.
- `blis` resolves to `1.3.x` with native wheels for Python 3.11–3.14.

All four Python versions in the supported matrix (3.11, 3.12, 3.13, 3.14) install from binary wheels with no compilation step.

## Alternatives considered

1. **Drop Python 3.13 and 3.14 from the supported matrix.** Rejected. Inconsistent with BILTIQ-000 decision §6 (4-version matrix declared at repo bootstrap) and `AGENT_RULES.md § Stack` ("Python 3.11, 3.12, 3.13, 3.14"). Long-term blocker — the library will need new-Python support as adoption grows; deferring it makes the gap harder to close later, not easier.

2. **Override `blis` to 1.3.x via a uv constraint while keeping en-core-web-sm 3.7.1.** Rejected on resolver grounds. `thinc 8.2.x` hard-pins `blis <0.8.0`. Forcing `blis 1.3` produces an unresolvable constraint set; uv and pip both refuse. Forking thinc to relax the pin is explicitly out of scope per the project brief ("never fork upstream").

3. **Hold the line — accept red CI on 3.13 and 3.14 cells until upstream ships compatible wheels for blis 0.7.x.** Rejected. AC7 of BILTIQ-001 prohibits `continue-on-error`; flipping red cells to "expected red" conditions the team to ignore CI signal, which is the wrong tradeoff for a library shipping privacy code to regulated consumers. Also, blis 0.7.x is a maintenance-mode line — wheels for new Python versions are unlikely to ship retroactively.

4. **Path A from plan.html Risk #1 — accept slow source builds on 3.13 and 3.14.** Rejected after the source build actually failed (gcc / AVX-512 kernel compile error on the dev machine, and presumably on GitHub Actions ubuntu-latest too). Path A only worked as a paper mitigation when wheels were the variable; with the source-build path itself broken, no version of the 0.7.x line is reachable on 3.13. The bump is the cleanest unblock.

## Consequences

**Positive:**
- 4-version matrix (3.11, 3.12, 3.13, 3.14) installs with binary wheels end-to-end. Cold install drops from ~3-5 min source-build time on 3.13/3.14 to ~30-60 seconds (per the en-core-web-sm download being the long pole).
- CI runs faster: no gcc / compiler toolchain dependency on the runner, no AVX-512-specific failure modes.
- Newer spaCy chain (3.8.x / thinc 8.3.x) is the actively maintained line. blis 1.3.x receives current wheel support; staying on 0.7.x meant inheriting a maintenance-mode dep.
- Plan.html Risk #1 mitigation upgrades from "Path A — accept source builds" to "wheels available on all 4 versions" — risk severity drops from HIGH to LOW.

**Negative / risks:**
- Future en-core-web-sm releases (3.9.x, 4.x) will repeat this question. We need to track Explosion's release cadence vs Python release cadence as a known maintenance item, not a surprise. Suggested cadence: re-validate the pin against the latest Python minor at every quarterly architecture review.
- The model file itself differs between 3.7.1 and 3.8.0 — slightly different weights, possibly slightly different NER outputs on edge cases. Not a concern at BILTIQ-001 (no engine code yet) but worth noting for BILTIQ-002+ when recogniser tests land. Golden-corpus tests in recogniser-port tasks should re-baseline against 3.8.0 outputs from the start, not 3.7.1.
- Consumers of `biltiq-privacy` who already have a pinned `en-core-web-sm 3.7.1` somewhere else in their environment will see a resolver conflict on upgrade. They will need to clean their local pin or accept the bump.

**Tech debt accepted:**
- The model version is documented in two places (pyproject.toml and approved-versions.md). A future helper could read approved-versions.md and generate the pyproject string, but that level of automation is not justified at this repo size. Discipline: update both in the same commit.

## References

- [`docs/specs/BILTIQ-001/spec.html`](../specs/BILTIQ-001/spec.html) — AC2 (NER model pin) and AC4 (4-version matrix).
- [`docs/specs/BILTIQ-001/design.html`](../specs/BILTIQ-001/design.html) § Risks R1 (the source-build escalation contract).
- [`docs/specs/BILTIQ-001/plan.html`](../specs/BILTIQ-001/plan.html) § Risks R1.
- [`docs/architecture/approved-versions.md`](../architecture/approved-versions.md) § Hard dependency pins (updated in this PR).
- [`docs/adr/0001-dual-install-paths.md`](0001-dual-install-paths.md) — preserves the `allow-direct-references` posture this pin depends on.
- 2026-05-17 dev conversation locking the bump after the 3.13 install failure during Step 2 verification.
- blis 1.3.3 wheel matrix on PyPI: cp312/cp313/cp314 all available.
