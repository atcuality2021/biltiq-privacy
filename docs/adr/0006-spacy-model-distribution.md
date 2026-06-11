# ADR 0006: spaCy model distribution — bundled for dev/CI, post-install for consumers

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** @atcuality2021
**Related task:** BILTIQ-012
**Amends:** the 2026-05-17 onboarding decision "spaCy model bundled" (see ADR-0002 for the version pin, which is unchanged)

## Context

Since BILTIQ-001, `packages/python-core/pyproject.toml` declared the NER model as a
direct-URL runtime dependency:

```toml
"en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0.tar.gz"
```

That worked for every install path we had exercised (editable, uv workspace, CI) —
but BILTIQ-012's AC5 publishes v0.1.0 to PyPI, and **PyPI (Warehouse) rejects any
upload whose metadata contains a direct-URL `Requires-Dist`** ("Can't have direct
dependency"). Hatchling's `allow-direct-references = true` only permits *building*
such a dist, not uploading it. spaCy models are not published to PyPI at all, so
there is no index-resolvable form of this dependency — the direct URL cannot be
"fixed", only moved out of the published metadata. Caught by the plan-reviewer in
BILTIQ-012 planning round 1, before anything reached the index.

## Decision

Dev ruling 2026-06-11 ("options 1 and 3 both"):

1. **The published dist ships without the model.** `en-core-web-sm` is removed from
   `[project].dependencies`. The wheel/sdist METADATA contains no direct-URL
   `Requires-Dist` (gate-checked at Build: `unzip -p dist/*.whl '*/METADATA' |
   grep 'Requires-Dist.*@'` must match nothing).
2. **The dev/CI path keeps the model bundled.** The direct URL moves to the
   repo-root `[dependency-groups].dev` (PEP 735 groups never reach published
   metadata), and `ci.yml` installs the tarball explicitly. Contributor workflow
   (`uv sync`) is unchanged.
3. **Consumers get two remedies, both documented in `MissingNERModelError`:**
   - a one-line post-install: `python -m spacy download en_core_web_sm`;
   - opt-in self-service: `PresidioDetector(auto_download_model=True)` downloads
     the model on the first `detect()` call that finds it absent.

### Compliance gating (`on_prem_preferred`)

`auto_download_model` defaults to **False**. The default library path performs no
network call — pinned by `test_default_path_makes_no_network_call`. The download is
an explicit, per-instance opt-in; airgapped deployments use the post-install (or a
vendored tarball) and never touch the flag. This keeps the library adoptable
unmodified under `on_prem_required` consumers.

## Alternatives considered

- **Tag-only release (defer publish):** solves nothing — the constraint bites at
  every future publish; better to fix packaging once, now.
- **`pip install biltiq-privacy[model]` extra:** optional-dependencies are part of
  published metadata, so a direct-URL entry there is rejected identically.
- **Re-host the model on PyPI under our namespace:** licence-compatible (MIT) but
  makes us the distribution channel for Explosion's artefact — maintenance burden
  and version-skew risk for zero UX gain over the post-install line.
- **Always auto-download (no flag):** unacceptable under `on_prem_preferred`; a
  silent network call from library code is the exact behaviour this repo's
  compliance mode exists to prevent.

## Consequences

- `pip install biltiq-privacy` is one step away from working detection; the error
  message closes that gap actionably. README documents the post-install line
  immediately after the install command.
- `MissingNERModelError` is now a *normal first-run state* for index consumers,
  not just a broken-environment signal — its message carries both remedies.
- Native SDKs (Node/PHP/Go) are unaffected: they talk to the sidecar, which is
  installed via the dev/operator path where the model is provisioned explicitly.
- `approved-versions.md`'s hard-pins block reflects the split (runtime deps vs
  dev-group model pin); ADR-0002's version pin (3.8.0) is unchanged.
