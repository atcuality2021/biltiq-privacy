# Stack — Libraries, Wrappers, and Utilities

**Purpose:** The catalog of what already exists in this repo. Read this **before writing any new utility, client, or wrapper** — Anti-Pattern #1 (Duplication) and #2 (Abstraction Bypass) defenses.

**Update rules:**
- Every new utility / wrapper added to the repo gets an entry here in the same PR.
- Every wrapper that becomes deprecated moves to `## Deprecated` with the replacement noted.
- Reviewed monthly alongside `overview.md`.

> **Note:** This repo is a **library + sidecar**, not a service. Many "typical" stack rows (DB, vector store, object storage, cache, queue) are intentionally absent — the library is stateless and consumers handle persistence. Do not add them without an ADR.

---

## Languages & runtimes

- **Python 3.11, 3.12, 3.13, 3.14** — `requires-python = ">=3.11"`. CI matrix covers all four.
- Node 20+ (only in `packages/node/`, v0.1.1+).
- PHP 8.2+ (only in `packages/php/`, v0.1.1+).
- Go 1.22+ (only in `packages/go/`, v0.1.1+).

---

## Library framework: NONE (intentional)

The library core (`packages/python-core/biltiq_privacy/`) is framework-free. No FastAPI, no Starlette, no Pydantic-Settings, no SQLAlchemy. Pure functions and small classes. **This is a hard rule; PRs adding framework deps to the library are auto-blocked in code review without an overriding ADR.**

---

## Server framework (sidecar only — `packages/python-server/`)

- **FastAPI ≥ 0.110** — REST sidecar exposing `/anonymize`, `/validate`, `/healthz`, `/openapi.json`.
- **uvicorn ≥ 0.27** — ASGI runtime; CLI `biltiq-privacy-server serve`.
- **pydantic v2** — request/response models. Use `model_validate` / `model_dump`, not `.parse_obj` / `.dict`.

---

## PII detection engine

- **presidio-analyzer ≥ 2.2, < 3** — depended on, never forked. Vendored in `vendor/presidio/` for airgap CI.
- **presidio-anonymizer ≥ 2.2, < 3** — same.
- **spacy ≥ 3.7** + **en_core_web_sm** — NER model bundled via pyproject dep on `en-core-web-sm`.

Extension points used:
- `presidio_analyzer.PatternRecognizer` — for the 8 Indian recognisers (Aadhaar, PAN, ABHA, GSTIN, Voter, IFSC, phone, Medical Registration; BILTIQ-002) and future EU/US/UK packs.
- `presidio_analyzer.EntityRecognizer` — base class for any ML/contextual recogniser (v0.4.0+).
- `presidio_anonymizer.operators.Operator` — for our HMAC-token pseudonymiser.

---

## Encryption (v0.5.0+)

- **age (system binary)** — wrapped via `subprocess.Popen` for streaming `pg_dump | age` pipelines. Pin: age ≥ 1.2.0. Wrapper at `biltiq_privacy.backup.age_stream` (BILTIQ-004); install via `scripts/install-age.sh` (autodetect) or `docs/runbooks/install-age.md` (manual).

---

## Internal modules — use these, do not duplicate

| What | Module | Purpose |
|---|---|---|
| Indian PII regex set + pure-stdlib redactor | `biltiq_privacy.indian.patterns` (BILTIQ-002) | Eight `Final[str]` constants (Aadhaar, PAN, ABHA, GSTIN, Voter ID, IFSC, Phone, Medical Registration), compiled `PATTERNS` dict, and `redact()` honouring `_REDACT_ORDER` (ABHA before AADHAAR). No Presidio / spaCy import — light enough for logging-filter use. |
| Indian Presidio adapter + engine factory | `biltiq_privacy.indian.recognisers.build_engine(nlp_engine=None)` (BILTIQ-002) | Builds a fresh `AnalyzerEngine` with the eight Indian `PatternRecognizer`s registered. Default-None branch constructs `NlpEngineProvider` pinned to `en_core_web_sm` (ADR-0002). No module-global singleton. |
| Logging redaction | `biltiq_privacy.core.log_filter.RedactionFilter` | `logging.Filter` subclass — scrubs `record.msg`, `record.args`, `extra=` fields. |
| HMAC pseudonymisation | `biltiq_privacy.core.doc_hasher.hmac_pseudonymise(value, *, key)` (BILTIQ-007) | Key is a keyword-only `bytes \| str` (str utf-8-encoded), never read from env inside `python-core`. No global state. Plus `hash_document`/`hash_text` (SHA-256). |
| Pseudonymiser (text → tokens) | `biltiq_privacy.core.pseudonymiser.Pseudonymiser(*, key)` (BILTIQ-007) | Key injected + validated in `__init__` (raises `HMACKeyRequiredError` on empty key). `make_token(entity_type, value, *, token_length=8)` → `[TYPE_<hex>]`; `pseudonymise_text` returns `(text, list[AuditRecord])`. |
| Generaliser (rule-based rollups) | `biltiq_privacy.core.generaliser` (BILTIQ-008) | Six field generalisers (`generalise_age` 20-year brackets, `generalise_date` → "Month YYYY", `generalise_location` state→region rollup, `generalise_phone`/`generalise_aadhaar`/`generalise_pan` suffix-mask) + `generalise_text(text, spans, *, region_map=None)` routing the 7-key `_GENERALISER` dispatch over `GeneralisationSpan` inputs. `region_map` is an inject-with-default seam (bundled Indian table; region-pack loader deferred to Phase C). Rule-based, NOT a dataset k-anonymity guarantee (measurement is BILTIQ-021). Stdlib + `re` only. |
| Audit hash-chain | `biltiq_privacy.core.audit_chain` — `append_row(prev_hash, payload)` / `verify_chain(rows)` + `GENESIS_PREV_HASH` (BILTIQ-010) | Pure, tamper-evident hash chain — **free functions, not an `AuditChain` class**. `append_row` returns a `ChainedRow` whose `hash` = `hash_text(prev_hash + canonical_json(payload))` (reuses `doc_hasher`); `verify_chain` → `VerifyReport{valid, first_broken_index}`, reporting tampering rather than raising. Caller-supplied timestamps (no clock read → deterministic); canonical JSON (`sort_keys=True`, compact separators, `ensure_ascii=False`) → cross-language verifiable (ADR-0005). No DB/SQLAlchemy/FastAPI import; consumers persist the rows. |
| Detector ABC + record | `biltiq_privacy.detectors.base.Detector` / `DetectedEntity` (BILTIQ-009) | `Detector.detect(text, language="en") -> list[DetectedEntity]` — the seam every backend implements. `DetectedEntity` is the 007 `Detection` TypedDict plus a `source` key (so it flows into the pseudonymiser unchanged — no parallel type). Framework-free: importing `base` loads neither Presidio nor spaCy. |
| Default detector | `biltiq_privacy.detectors.presidio_backend.PresidioDetector(*, score_threshold=0.5)` (BILTIQ-009) | Ports CDSCO's `detect_pii_rules()` behind the ABC, reusing `indian.recognisers.build_engine()` (no recogniser re-defined). Instance-level lazy singleton (engine built on first `detect()`); configurable threshold; six-key `DetectedEntity` projection with `source="presidio"` + `round(score,4)`. Presidio/spaCy imports are method-level (AC5); a missing `en_core_web_sm` raises `MissingNERModelError`. Re-exported from `biltiq_privacy.detectors`. |
| Regime ABC | `biltiq_privacy.regimes.base.Regime` | Implement to add a new regulatory framework. |
| Multi-region recogniser builder | `biltiq_privacy.recognisers.build_engine(regions=[...])` (v0.2.0+) | Convenience factory wrapping per-region adapters; planned for when EU/US/UK packs land. For Indian-only use today, call `biltiq_privacy.indian.recognisers.build_engine()` directly. |
| Memory-spine writer | `scripts._memory_writer.write_event(event_type, payload)` | POSIX-atomic append to `.biltiq/memory-stream.jsonl`; consumed by `scripts/_memory_curator.py` to project session signal into `MEMORY.md`. See `AGENT_RULES.md` § Memory. |
| age streaming wrapper | `biltiq_privacy.backup.age_stream.open_age_writer(out_path, *, recipient)` / `open_age_reader(in_path, *, identity_path)` (BILTIQ-004, v0.5.0+) | `@contextmanager` generators wrapping the system `age` binary via `subprocess.Popen`; yield pipe handles so plaintext never lands on disk (AC2/AC3 invariant, statically enforced by `tests/backup/test_no_intermediate_files.py`). Exception hierarchy: `AgeNotInstalledError(FileNotFoundError)` at `__enter__`, `AgeProcessError(subprocess.CalledProcessError)` at `__exit__` — both stdlib-subclassed so callers need not import the wrapper to handle errors. See ADR-0003. |

[PROJECT: add new internal modules here in the same PR they're created.]

---

## Shared utilities

| What | Module | Use when |
|---|---|---|
| UTC timestamp | `datetime.now(timezone.utc)` | Any timestamp. Do not `datetime.utcnow()` (deprecated). Consider a future `core.time` wrapper if usage proliferates. |
| Path manipulation | `pathlib.Path` | All filesystem paths. No `os.path`. |
| Logging | `logging.getLogger(__name__)` with `RedactionFilter` attached | All logging. No `print()` in library code. |
| Data classes | `@dataclass(slots=True, frozen=True)` for return types | Default for any return value in the library. |
| Type hints | `from __future__ import annotations` at top of every module | Strict mypy in CI. |

---

## Test fixtures

| Fixture | Module | Provides |
|---|---|---|
| `hmac_key` | `tests/conftest.py` | Deterministic 32-byte key for tests. Never the production key. |
| `sample_indian_pii` | `tests/fixtures/india.py` | Synthetic text blob embedding one known-fake value per Indian entity type (all eight), assembled from the `*_VALID` tuples — no real PII (BILTIQ-009). |
| `presidio_engine_indian` | `tests/fixtures/presidio.py` | Session-scoped `AnalyzerEngine` from `build_engine()`, pre-loaded with the eight Indian recognisers (BILTIQ-009). |
| _(none — by design)_ | — | `audit_chain` needs no fixture: the chain is built from pure, stateless free functions, so `tests/core/test_audit_chain.py` threads chains via a local `_build_chain` helper rather than a shared fixture (BILTIQ-010). |
| `fastapi_client` | `packages/python-server/tests/conftest.py` | `TestClient` against the FastAPI app — no real network. |

Tests must:
- Run with no network access (mark `pytest -m "not network"` as default).
- Use synthetic PII only — never real identifiers, never copied from real documents.
- Hit ≥ 90% line coverage on `core/` and `recognisers/`.

### Running tests

Two equivalent invocations:

- **Per-package (what CI runs):** `pytest packages/python-core/tests` or `pytest packages/python-server/tests`. CI's matrix uses this form (`pytest packages/${{ matrix.package }}/tests/`).
- **Repo-root (developer convenience):** bare `pytest` from `/`. Collects both package suites plus `tests/scripts/` (BILTIQ-003 memory-spine).

The repo-root invocation relies on three pieces of plumbing (added in BILTIQ-002 Step 9):

1. `[tool.pytest.ini_options].pythonpath` in `/pyproject.toml` puts both `packages/<pkg>/` roots on `sys.path` so `from biltiq_privacy.indian...` and `from tests.fixtures...` resolve.
2. `consider_namespace_packages = true` switches pytest's `--import-mode=importlib` from "synthesise parent package from directory walk" to "use Python's full import system" — required so the regular-package `packages/python-core/tests/__init__.py` is honoured. Without it, pytest synthesises a `tests` namespace pointing only at `<repo>/tests/` (which holds `tests/scripts/`) and `tests.fixtures` resolves to nothing.
3. `packages/python-core/tests/__init__.py` is a regular package (it owns the `tests.fixtures.india` module used by `test_patterns.py`). `packages/python-server/tests/` and `tests/scripts/` remain PEP 420 namespace dirs — pytest's importlib mode loads their test files anonymously, so they don't need `__init__.py`.

If you add a new package under `packages/`, append its root to the `pythonpath` list and decide whether its `tests/` needs an `__init__.py` (only if other test files import from it via a `tests.<subpath>` path).

---

## Deprecated

(none yet — repo is pre-implementation.)

| Deprecated | Replacement | Removal target |
|---|---|---|

---

## When to add a new wrapper

Add a wrapper when:
- The same external library is used in 3+ files with the same setup boilerplate.
- The external library has cross-cutting concerns (logging, retry, auth) that should be centralised.
- A behaviour would change project-wide if the library were swapped (good test: "could we move from `presidio-analyzer` to a custom engine without rewriting every caller?" — `Detector` ABC already isolates this).

When you add one:
1. Implement under `packages/python-core/biltiq_privacy/<category>/`.
2. List it in this file in the same PR.
3. The `code-reviewer` skill checks for new wrappers and flags missing entries here.

---

## Polyglot SDK stack (v0.1.1+)

Each native SDK in `packages/{node,php,go}/` is **deliberately thin**:

- HTTP client only (`fetch`, `Guzzle`, `net/http`).
- Configuration: `BILTIQ_PRIVACY_URL` env var (default `http://localhost:8088`) + auth header.
- Surface: one method per sidecar endpoint, language-idiomatic names.
- No business logic. Regime checks, recognisers, generalisation all happen in the Python sidecar.

SDKs are generated from `packages/python-server/openapi.json` via `openapi-generator` for the initial scaffold; hand-polished for ergonomics. Generator config lives at `scripts/sdk-gen/`.
