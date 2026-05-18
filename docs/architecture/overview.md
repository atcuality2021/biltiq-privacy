# Architecture Overview

**Repo:** biltiq-privacy
**Last reviewed:** 2026-05-17

## What this system does (1-paragraph)

biltiq-privacy is a reusable Python privacy/anonymisation/compliance package productised from CDSCO-RegAI. The engine detects and redacts PII (using Microsoft Presidio plus custom Indian/EU/US recognisers), pseudonymises with HMAC tokens, generalises with k-anonymity rollups, signs an append-only hash-chain audit log, and *attests against a regulatory framework* (DPDP 2023, GDPR, HIPAA, CCPA) via per-regime adapters. A separate FastAPI sidecar exposes REST `/anonymize` and `/validate` endpoints so Node, React, PHP, Go, and other non-Python consumers can use the engine without bundling Python. Thin native SDKs in each language (v0.1.1+) wrap the sidecar so consumers see a native-feeling package install.

## Components

```
biltiq-privacy/                                    (monorepo)
├── packages/
│   ├── python-core/      biltiq_privacy           library — engine, no framework deps
│   ├── python-server/    biltiq_privacy_server    FastAPI sidecar
│   ├── node/             @biltiq/privacy          thin HTTP SDK   (v0.1.1+)
│   ├── php/              biltiq/privacy           thin HTTP SDK   (v0.1.1+)
│   └── go/               github.com/biltiq/privacy-go              (v0.1.1+)
├── server/
│   └── docker/           Dockerfile, compose      optional containerisation
├── scripts/
│   ├── install-age.sh    OS-detection installer for `age` binary
│   └── install-server.sh native install helper (systemd unit + venv setup)
└── docs/                 BiltIQ canonical + regime guides
```

**`biltiq_privacy` (library, `packages/python-core/`):**
- `indian/patterns.py` — eight Final[str] regex constants (Aadhaar, PAN, ABHA, GSTIN, Voter ID, IFSC, Phone, Medical Registration), compiled PATTERNS dict, and pure-stdlib `redact()` (BILTIQ-002, v0.1.1+).
- `core/log_filter.py` — `_RedactionFilter` for `logging` integration.
- `core/doc_hasher.py` — HMAC pseudonymisation (key as constructor arg).
- `core/pseudonymiser.py` — replaces detected PII with deterministic HMAC tokens.
- `core/generaliser.py` — 20-year age brackets + state→region rollup (k-anonymity).
- `core/audit_chain.py` — append-only hash chain; pure hashing logic, consumers persist.
- `indian/recognisers.py` — eight Presidio `PatternRecognizer`s + `build_engine()` factory (BILTIQ-002, v0.1.1+).
- `{eu,us,uk}/recognisers.py` — EU/US/UK PII (v0.2.0+; same sub-package layout).
- `regimes/base.py` — `Regime` ABC + `ComplianceCheck` / `ComplianceReport` dataclasses.
- `regimes/dpdp.py` — 8-check DPDP/NDHM/ICMR validator (v0.1.0).
- `regimes/{gdpr,hipaa,ccpa}.py` — additional regimes (v0.2.0+).
- `detectors/base.py` — `Detector` ABC.
- `detectors/presidio_backend.py` — default Presidio-backed detector.
- `detectors/{llm_backend,hybrid}.py` — contextual + ensemble (v0.4.0+).
- `backup/{age_pipeline,manifest}.py` — `age`-based encrypted backup (v0.5.0+).

**`biltiq_privacy_server` (server, `packages/python-server/`):**
- `app.py` — FastAPI app with routes `/anonymize`, `/validate`, `/healthz`, `/openapi.json`.
- `models.py` — pydantic request/response schemas.
- `cli.py` — `biltiq-privacy-server serve [--host --port --workers]`.
- Depends on `biltiq-privacy`; injects HMAC key + regime selection from env.

**Native SDKs (`packages/{node,php,go}/`, v0.1.1+):**
- Auto-discover sidecar at `BILTIQ_PRIVACY_URL` (default `http://localhost:8088`).
- Wrap `/anonymize` and `/validate` into language-native API surfaces.
- Generated from the OpenAPI spec emitted by FastAPI.

**`scripts/` (tooling tier — outside `pyproject.toml`):**
`scripts/_memory_writer.py` and `scripts/_memory_curator.py` form the **memory spine** — a per-machine append-only event stream (`.biltiq/memory-stream.jsonl`) plus a projector that splice-rewrites curator-owned blocks in `MEMORY.md`. Not part of the published `biltiq-privacy` wheel; consumed only by repo-local engineering skills (`/biltiq-engineering:standup`, `/biltiq-engineering:reflect`) and the opt-in `post-commit` hook. Contract documented in `AGENT_RULES.md` § Memory.

## Data flow

```
                         ┌─ Python consumer ─→ import biltiq_privacy ──┐
                         │                                              │
[client app]             ├─ Node / PHP / Go / React ─→ thin SDK ──┐    │
                         │                                         │    │
                         └─ curl / Postman ─→ raw HTTP ────────────┤    │
                                                                    ▼    ▼
                                            ┌──────────────────────────────────┐
                                            │ biltiq_privacy_server (FastAPI)  │
                                            │   POST /anonymize                │
                                            │   POST /validate                 │
                                            └──────────────────┬───────────────┘
                                                               ▼
                                            ┌──────────────────────────────────┐
                                            │ biltiq_privacy (library)         │
                                            │   ┌─────────────────┐            │
                                            │   │ Detector        │ ← Presidio │
                                            │   │  → entities     │   engine   │
                                            │   └────────┬────────┘            │
                                            │            ▼                     │
                                            │   ┌─────────────────┐            │
                                            │   │ Pseudonymiser   │ ← HMAC key │
                                            │   │  → tokens       │   (config) │
                                            │   └────────┬────────┘            │
                                            │            ▼                     │
                                            │   ┌─────────────────┐            │
                                            │   │ Generaliser     │            │
                                            │   │  → k-anonymous  │            │
                                            │   └────────┬────────┘            │
                                            │            ▼                     │
                                            │   ┌─────────────────┐            │
                                            │   │ Regime          │ ← DPDP /   │
                                            │   │  → ComplianceReport   GDPR / │
                                            │   └────────┬────────┘   HIPAA    │
                                            │            ▼                     │
                                            │   ┌─────────────────┐            │
                                            │   │ AuditChain      │            │
                                            │   │  → hash-row     │            │
                                            │   └─────────────────┘            │
                                            └──────────────────────────────────┘
```

Latency budget (warm path, native install, Indian recogniser set):
- HTTP round-trip: ~1-5 ms (localhost).
- Detection (Presidio + spaCy `en_core_web_sm`): ~10-40 ms per kilobyte of text.
- Pseudonymisation + generalisation + audit row: <1 ms.
- Total typical: ~15-50 ms warm. Cold start (spaCy model load): ~2-4 s.

## Deployment topology

The library has no deployment story — it's a pip dependency. The server has two deployment paths, both producing identical REST endpoints:

**Native (preferred):**
```bash
# Production
sudo apt install age                              # or brew install age / dnf install age
pip install biltiq-privacy-server[full]
biltiq-privacy-server serve --host 0.0.0.0 --port 8088 --workers 4
# OR run under systemd via the included unit template
```
Memory footprint: ~120 MB resident (uvicorn + Python + Presidio + `en_core_web_sm`).

**Docker (offered):**
```bash
docker run -d -p 8088:8088 \
  -e BILTIQ_PRIVACY_HMAC_KEY=... \
  biltiq/privacy-server:0.1.0
```
Image size: ~500 MB. Memory: ~350 MB.

Both expose `POST /anonymize`, `POST /validate`, `GET /healthz`, `GET /openapi.json` at `:8088`.

## Dependencies

External services this repo depends on:
- **presidio-analyzer ≥ 2.2, < 3** — PII detection engine. Pinned, vendored in `vendor/presidio/` for airgap CI. Never forked.
- **presidio-anonymizer ≥ 2.2, < 3** — anonymisation operators. Same pinning policy.
- **spacy + en_core_web_sm** — NER model bundled via pyproject dep.
- **age** (system binary) — encryption (v0.5.0+). Install via `scripts/install-age.sh`.
- **rapidfuzz** (MIT) — fuzzy string distance if needed. **Never** `python-Levenshtein` (GPL).

Internal services this repo depends on: none. The library is leaf-of-tree.

Services that depend on this repo:
- **CDSCO-RegAI** — first consumer; source of the ported privacy stack. Internal repo; not public.
- ATC CommandCenter — confirmed consumer.
- ManthanQuant — confirmed consumer.
- Future BiltIQ products handling PII.

## Failure modes

| Dependency | Failure | This system's behavior |
|---|---|---|
| Presidio import error | install incomplete | Library raises `BiltiqPrivacyImportError` on first use; server returns 503 with diagnostic from `/healthz`. |
| spaCy model missing | `en_core_web_sm` not installed | Library raises `MissingNERModelError` with install instructions; server `/healthz` returns 503. |
| `age` binary missing | not on PATH | Backup module (v0.5.0+) raises `AgeBinaryNotFoundError`; v0.1.0 unaffected. |
| Detector failure | upstream Presidio bug / OOM | Server returns 500 with hash-chain-logged audit row. No silent failure. |
| HMAC key not set | env / config missing | Library raises `HMACKeyRequiredError` at constructor time, before any text is processed. |
| Sidecar unreachable | SDK side | Native SDKs raise language-native connection error; consumer decides retry policy. |

## Where new code goes

The most common "where do I put this?" answers:

- A new PII recogniser pack for region X → sub-package `packages/python-core/biltiq_privacy/<region>/` containing `patterns.py` (pure-stdlib regex + `redact()`) and `recognisers.py` (Presidio adapter + `build_engine()`); tests in `packages/python-core/tests/<region>/`. The `indian/` pack (BILTIQ-002) is the canonical reference.
- A new regime adapter → `packages/python-core/biltiq_privacy/regimes/<regime>.py` implementing `Regime` ABC + tests.
- A new detector backend → `packages/python-core/biltiq_privacy/detectors/<name>.py` implementing `Detector` ABC.
- A new REST endpoint → `packages/python-server/biltiq_privacy_server/app.py` (route) + `models.py` (schema) + tests in `packages/python-server/tests/`.
- A new shared utility for the library → `packages/python-core/biltiq_privacy/core/<name>.py` + update `docs/architecture/stack.md`.
- A new helper script → `scripts/<name>.sh` (POSIX, OS-detection if needed).
- A new SDK method → `packages/<lang>/src/...` (v0.1.1+).

**Forbidden placements:**
- FastAPI / Starlette / uvicorn imports in `packages/python-core/` — auto-blocked in code review.
- HMAC key reading from env inside `packages/python-core/` — constructor-arg only.
- Hardcoded vLLM / OpenAI / Anthropic endpoints anywhere — consumer-injected client argument only.

## Audit cadence

This file is reviewed monthly. Material changes (new package, dropped dependency, deploy topology change, fork policy change) require a same-PR update plus an ADR if it overrides any of the 10 decisions in `[[memory:project-architecture-decisions]]`.
