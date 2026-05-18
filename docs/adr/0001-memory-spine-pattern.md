# ADR 0001: Memory-spine pattern — JSONL event stream + projected MEMORY.md

**Status:** accepted
**Date:** 2026-05-18
**Deciders:** @don007rvs
**Related task:** BILTIQ-003

## Context

Several `biltiq-engineering` workflow commands (`/standup`, `/reflect`, `/commit`, and the planned compaction auto-trigger) emit structured events about engineering activity — daily standups, decisions, blockers, reflection notes, commit metadata. These events need to survive across Claude Code sessions so that `MEMORY.md` — the file injected into every session's context — stays current without manual curation.

Three coupled choices fall out of this:

1. Where the event log lives and what shape it takes.
2. Where the projection code (writer + curator) lives, given that `biltiq-privacy` is a library distributed to public PyPI.
3. How the curator updates `MEMORY.md` without trampling content the dev has hand-curated.

This ADR captures all three as one cohesive pattern because they are designed against the same contract — the upstream plugin's call sites assume all three exist together.

## Decision

**(1) Event stream: per-machine, append-only JSONL at `.biltiq/memory-stream.jsonl`.** Gitignored. One event per newline-delimited JSON object, with fields `schema_version` (int), `ts` (ISO-8601 UTC), `event_type` (snake_case string), and `payload` (dict). Single events are capped at 4 KiB (`PIPE_BUF` on Linux) so a single `os.write()` with `O_APPEND` is POSIX-atomic against concurrent writers. This convention already exists in this repo: `.biltiq/estimates-history.jsonl` (reflect-skill telemetry) uses the same shape. The committed canonical projection is `MEMORY.md`; the stream is a regenerable per-machine buffer.

**(2) `scripts/` tier — developer tooling, not library code.** `scripts/_memory_writer.py` and `scripts/_memory_curator.py` live outside `packages/python-core/biltiq_privacy/` and are excluded from `pyproject.toml`'s package configuration. They are stdlib-only, run only on developer machines, and never ship to PyPI. The upstream `biltiq-engineering` plugin imports them via `from scripts._memory_writer import write_event` — that import path is the public contract.

**(3) MEMORY.md `auto:` / `manual:` marker contract.** Auto-curated content lives between paired HTML comments:
```
<!-- auto:<section_name>:start -->
(generated; do not hand-edit)
<!-- auto:<section_name>:end -->
```
Manual content is delimited symmetrically with `<!-- manual:start -->` / `<!-- manual:end -->`. The curator rewrites only `auto:` blocks; everything else (including the top-of-file preamble and the `manual:` block contents) is copied through verbatim. If any expected marker pair is missing, the curator **fails closed** — exits non-zero, writes nothing, surfaces the marker name on stderr.

## Alternatives considered

1. **SQLite-backed event store** — Rejected. Adds query power we won't use in v1, turns a grep-able text file into an opaque binary, and complicates the gitignore + per-machine backup story. JSONL is enough until filtered projections become a real requirement.
2. **User-global stream at `~/.biltiq/<repo>/memory-stream.jsonl`** — Rejected. Survives reclone but per-machine — work on a laptop + desktop diverges. `MEMORY.md` (committed) already plays the cross-machine canonical role; making the stream per-clone keeps the trust boundary simple. (Spec OQ1.)
3. **Distributing the writer + curator as part of the library** — Rejected. The library is framework-free and shipped to PyPI; adding developer-workflow tooling to the published artifact would bloat the install for end-users who don't run the BiltIQ workflow. `scripts/` as a sibling directory keeps the boundary clean.
4. **Regex-based section markers in MEMORY.md** — Rejected. Brittle when the dev edits the file from the inside; one stray bracket and the regex consumes manual content. HTML-comment markers are invisible to Markdown renderers, easy to grep, and the fail-closed rule protects manual content from any future regex mishap.
5. **Read-modify-write of MEMORY.md without explicit markers** — Rejected. Auto-detection of "which paragraphs are mine to rewrite" cannot be made safe against a dev editing the file between curator runs. Explicit out-of-band markers force a contract.
6. **`filelock` PyPI package for curator concurrency** — Rejected. New runtime dependency for what stdlib `fcntl.flock` already does on Linux/macOS (the only supported dev platforms per `MEMORY.md`). Adds a wheel + version pin + airgap-CI burden against a feature that hasn't been requested.

## Consequences

**Positive:**
- Workflow commands persist state across sessions without each command re-implementing a write path.
- `MEMORY.md` stays current automatically while remaining a regular text file the dev can read, diff, and hand-edit.
- Per-machine stream eats our own dogfood — `biltiq-privacy` exists to prevent leakage of dev-authored prose; keeping the stream local-only honours that posture.
- Stdlib-only implementation: zero new runtime dependencies, trivially compliant with `on_prem_preferred` mode.
- Append is O(1); curator runs once per commit at most. Performance budget is `< 200 ms` for streams up to ~10k events.

**Negative / risks:**
- The stream is per-machine — moving development to a fresh clone loses the local event history. Acceptable because `MEMORY.md` (committed) is the canonical longitudinal record; the stream is a buffer.
- Fail-closed marker behaviour means a hand-edit that breaks the markers stalls the curator until fixed. Trade-off accepted because the alternative (best-effort rewrite) risks corrupting manual content.
- The 4 KiB per-event cap is a hard limit. Events that need more bytes have to be split, or trigger a stream-format v2 (which is why `schema_version` exists from day one).
- Coupling the upstream plugin's call sites to a specific import path (`from scripts._memory_writer import write_event`) means renaming this module is a breaking change for the plugin. Documented in `AGENT_RULES.md § Memory`.

**Tech debt accepted:**
- The curator rebuilds auto-sections from the full stream on every run, not incrementally. Fine until streams exceed ~10k events; incremental projection is a deferred follow-up.
- No event archival yet — `.biltiq/memory-stream.jsonl` grows monotonically. Acceptable for solo-dev usage; multi-dev or long-horizon usage will need a rotation policy.
- The opt-in `post-commit` hook swallows curator failures (logs but never aborts the commit). Devs running curation on-demand get unmuted errors; hook users have to read the log to notice silent failures. Trade-off accepted because aborting commits on a tooling failure would be worse.

## References

- `docs/specs/BILTIQ-003/spec.html` — acceptance criteria (AC1–AC9), open-question resolutions (OQ1, OQ2).
- `docs/specs/BILTIQ-003/design.html` — full design including 6 alternatives table, security & compliance notes, file-by-file enumeration.
- `docs/specs/BILTIQ-003/plan.html` — 6 atomic build steps with tests per AC.
- `docs/architecture/stack.md § Internal modules` — registration of `scripts._memory_writer.write_event` (added in Step 4 of the build plan).
- `AGENT_RULES.md § Memory` — public contract documentation (added in Step 4).
- BILTIQ-engineering plugin internals — task IDs `BILTIQ-017a` (Python core, this work's upstream sibling) and `BILTIQ-017g-phase2` (compaction auto-trigger, deferred).
