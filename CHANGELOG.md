# Changelog

All notable changes to this project are documented here. Format mirrors [Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

- feat: core hashing & HMAC pseudonymiser — `biltiq_privacy.core.doc_hasher` (`hash_document`, `hash_text` SHA-256; `hmac_pseudonymise(value, *, key)` HMAC-SHA256 with the key as a keyword-only `bytes | str`, never read from env inside `python-core`), `biltiq_privacy.core.pseudonymiser.Pseudonymiser` (key bound + validated in `__init__`, raising `HMACKeyRequiredError` on an empty key before any text; `make_token(entity_type, value, *, token_length=8)` producing `[TYPE_<hex>]`; `pseudonymise_text` with `Detection`/`AuditRecord` TypedDicts, end→start replacement, restored audit order), and `biltiq_privacy.core.exceptions.HMACKeyRequiredError(ValueError)`; 16 tests covering AC1–AC5 with golden-digest characterization against CDSCO behaviour; added the `hmac_key` test fixture reserved in `stack.md` (BILTIQ-007)
- feat: Indian PII recogniser pack — `biltiq_privacy.indian.patterns` (eight `Final[str]` regex constants for Aadhaar, PAN, ABHA, GSTIN, Voter ID, IFSC, Phone, Medical Registration + compiled `PATTERNS` dict + pure-stdlib `redact()` honouring `_REDACT_ORDER` ABHA-before-AADHAAR) and `biltiq_privacy.indian.recognisers` (eight Presidio `PatternRecognizer`s, `INDIAN_RECOGNISERS` tuple, `build_engine()` factory pinned to `en_core_web_sm`); 95 tests covering AC1/AC2/AC3/AC4/AC5/AC6/AC7/AC11; CDSCO-RegAI source attribution in module docstrings; lazy-import contract proven by subprocess test (importing `patterns` does not load presidio or spaCy) (BILTIQ-002)
- chore: repo-root pytest collection — added `consider_namespace_packages = true` + `pythonpath` to root `pyproject.toml`, restored regular-package `packages/python-core/tests/__init__.py`, and added a no-op repo-root `conftest.py` anchor so bare `pytest` from `/` collects all three test trees (python-core, python-server, `tests/scripts/`) without the prior `tests.fixtures` namespace collision; per-package CI invocation unchanged. Documented in `docs/architecture/stack.md` § Running tests (BILTIQ-002)
- chore: include `tests/scripts` in root `pyproject.toml` `[tool.pytest.ini_options].testpaths` so bare `pytest` from the repo root collects the BILTIQ-003 memory-spine tests alongside the two package suites — 34 tests + 1 skipped (BILTIQ-003 tech-debt #4 close-out)
- feat: memory-spine tooling — append-only JSONL event stream at `.biltiq/memory-stream.jsonl` (per-machine, gitignored), curator that projects events into `MEMORY.md` between `auto:<name>:start/end` markers with fail-closed semantics, and an opt-in `post-commit` hook + installer that runs the curator in the background without aborting commits on failure (BILTIQ-003)
- feat: pyproject + monorepo packages/ skeleton with dual pip + uv install paths (BILTIQ-001)
- fix: biltiq-gates.yml job names truncated by unquoted YAML `#`; extract banned-vocab filter to scripts/check-banned-vocab.py (BILTIQ-000)

## [0.1.0] - YYYY-MM-DD

- feat: initial repo bootstrap (BILTIQ-000)
