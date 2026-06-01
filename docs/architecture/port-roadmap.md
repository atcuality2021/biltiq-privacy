# Port roadmap — CDSCO-RegAI privacy engine → biltiq-privacy

**Status:** approved 2026-06-01 (brainstorm). North-star for the skeleton→production build-out.
**Goal:** every `overview.md` module exists as a tested, self-contained biltiq-privacy module with **zero runtime dependency on the cdcso repo**. CDSCO-RegAI is the *source material*; biltiq-privacy is the standalone MIT/PyPI product.

## Approach

Port by **decoupling, not rewriting**. Lift each CDSCO module, strip app coupling into injected arguments (HMAC key → constructor arg; LLM → injected callable; PDF → caller passes text; DB persistence → caller's concern, library emits pure hash rows), genericise CDSCO/India-specifics behind the region/regime sub-package pattern, and pin behaviour with characterization tests. Sequence strictly by the dependency chain; ship a publishable **v0.1.0 library first**, then server, then breadth, then advanced detection + SDKs.

## Source inventory (CDSCO-RegAI)

~1,000–1,100 LOC of portable privacy logic, mostly pure (stdlib + Presidio/spaCy):

| CDSCO source | LOC | Target module | Coupling to strip |
|---|---|---|---|
| `utils/doc_hasher.py` | 22 | `core/doc_hasher.py` | `settings.HMAC_KEY` → constructor arg |
| `anonymisation/pseudonymiser.py` | 37 | `core/pseudonymiser.py` | (via doc_hasher) |
| `anonymisation/generaliser.py` | 112 | `core/generaliser.py` | none (pure) |
| `anonymisation/presidio_engine.py` | 130 | `detectors/presidio_backend.py` | reuse BILTIQ-002 `build_engine()` |
| `modules/audit.py` | 305 (~50 pure) | `core/audit_chain.py` | SQLAlchemy/session → persistence interface |
| `compliance/dpdp_validator.py` + `utils/pii_patterns.py` | 200 | `regimes/dpdp.py` + `regimes/base.py` | none (pure) |
| `anonymisation/pipeline.py` | 149 | top-level `anonymise()` | PDF extractor, LLM call → injected |
| `anonymisation/contextual_detector.py` | 72 | `detectors/llm_backend.py` | MedGemma client → injected callable |
| `evaluation/anonymisation_metrics.py` | 85 | `evaluation/metrics.py` | pandas/scipy (optional extra) |
| `compliance/responsible_ai.py` | 226 | *deferred* | CDSCO-specific model cards |
| `routers/{anonymise,compliance}.py` | 235 | *stay in CDSCO* | FastAPI; CDSCO imports biltiq-privacy |

## Phased program

### Phase A — Core library pipeline → tag `v0.1.0` *(critical path)*
- **BILTIQ-007** `core/doc_hasher` + `core/pseudonymiser` (HMAC, key as constructor arg). S
- **BILTIQ-008** `core/generaliser` (age/date/location rollups). S/M
- **BILTIQ-009** `detectors/base` (ABC) + `detectors/presidio_backend` (reuses 002). M
- **BILTIQ-010** `core/audit_chain` (pure hash-chain; consumers persist). S/M
- **BILTIQ-011** `regimes/base` + `regimes/dpdp` (8 checks). M — *high-risk: compliance*
- **BILTIQ-012** top-level `anonymise()` + public API + integration tests → **v0.1.0**. M

### Phase B — REST sidecar → `v0.2.0`
- **BILTIQ-013** `python-server`: `app.py` (`/anonymize`, `/validate`, `/healthz`), `models.py`, `cli.py`. Built clean (CDSCO routers stay in CDSCO). M/L

### Phase C — Breadth (regimes + region packs)
- **BILTIQ-014/015/016** EU / US / UK recogniser packs (mirror `indian/`).
- **BILTIQ-017/018/019** GDPR / HIPAA / CCPA regimes.

### Phase D — Advanced detection *(needs ADR — external AI)*
- **BILTIQ-020** `detectors/llm_backend` (consumer-injected callable, no hardcoded endpoint) + `detectors/hybrid` + **ADR** per `on_prem_preferred`.
- **BILTIQ-021** `evaluation/metrics` — k-anonymity / l-diversity / t-closeness / F1 (optional extra).

### Phase E — Native SDKs (`v0.1.1`+; depend on B's OpenAPI)
- **BILTIQ-022/023/024** Node / PHP / Go thin HTTP SDKs.

### Phase F — Backup (after PR #5 / BILTIQ-004 merges)
- **BILTIQ-025** `backup/age_pipeline` + `manifest` on the BILTIQ-004 `age` wrapper.

## Deferred / out of scope (this program)
- `responsible_ai` (fairness, model cards, transparency) — CDSCO-specific; genericise later or drop.
- Reversible-token vaulting, batch/streaming APIs, sidecar auth — follow-ups.

## Constraints
- **Compliance:** `on_prem_preferred`. Deterministic core needs no ADR; **Phase D requires an ADR**. No hardcoded AI endpoints — consumer-injected only (`overview.md` forbidden placements).
- **Performance:** ~15–50 ms warm; cold start ~2–4 s (spaCy load).
- **Security:** PII crosses the trust boundary; HMAC key constructor-arg only (never env in `python-core`); audit rows tamper-evident.

## Risks
- **Audit decoupling** (DB→pure) is the trickiest extraction → BILTIQ-010 ships hash-chain as pure functions + documented persistence interface; CDSCO keeps its DB writer.
- **k-anonymity semantics** — the generaliser applies rules, it does not *guarantee* k across a dataset (that is the metrics module, Phase D) → documented explicitly in BILTIQ-008/012, no overclaiming.
- **Behaviour drift from CDSCO** → port characterization tests alongside each module.

## Alternatives considered
1. Greenfield rewrite — rejected: discards proven, regulator-reviewed logic; behaviour-drift risk.
2. Depend on cdcso as a library — rejected: violates leaf-of-tree + MIT/public-PyPI; cdcso is private.
3. Breadth-first walking skeleton — rejected (chose dependency order): no shippable artifact until the end.
