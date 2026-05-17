# biltiq-privacy — Bootstrap Brief

> **Paste this entire file as the first message in a fresh Claude Code session opened at `/home/atc/Desktop/biltiq-privacy/`.** Or use `/init` and reference this file. It is the only context the new session needs.

---

## 1. Mission

Reusable privacy / anonymisation / compliance Python package extracted from `CDSCO-RegAI`. Serves any project that handles PII subject to **DPDP 2023 (India)**, **GDPR (EU)**, **HIPAA (US)**, **CCPA (California)**, or future regimes. Currently three BiltIQ products will consume it: CDSCO-RegAI, ATC CommandCenter, ManthanQuant. More to follow.

The privacy logic in CDSCO-RegAI is already battle-tested (19/19 unit tests + presidio integration + audit hash-chain shipped on `main`). This package productises it.

---

## 2. Hard constraints — do not violate

1. **NEVER fork Presidio.** Depend on it: `presidio-analyzer>=2.2,<3`, `presidio-anonymizer>=2.2,<3`. The value of the package is *custom recognisers + regime validators + workflow*, not re-implementing what Microsoft maintains.
2. **NEVER fork `age`.** Treat as a system dependency. Wrap via `subprocess.Popen` for streaming pipelines (`pg_dump | age`). Document the install path per OS in the README; provide `scripts/install-age.sh` for convenience.
3. **License: MIT** throughout. Matches CDSCO-RegAI. Permissive so any consumer (including commercial) can use the package without copyleft concerns.
4. **Do not pull in AGPL or GPL dependencies.** Two specific avoidances:
   - `pymupdf` — AGPL-3.0. PDF extraction stays in *consuming* projects, not this library.
   - `python-Levenshtein` — GPL-2.0. If string-distance is needed, use `rapidfuzz` (MIT).
5. **Library-grade code only.** No FastAPI / SQLAlchemy / pydantic-settings dependencies. Pure functions and small classes. Consumers inject their own framework glue.
6. **Type hints everywhere.** `from __future__ import annotations`. No bare `Any`, no `# type: ignore` without a one-line inline justification.
7. **No banned vocabulary** in code, docs, or commit messages: "cutting-edge", "revolutionary", "empowering", "seamless", "future-ready". (Inherited from BiltIQ engineering rules.)
8. **Git push policy:** push to `git@github.com:atcuality2021/biltiq-privacy.git` only. Never push to any Aarna-Tech org repo. (Same rule as CDSCO-RegAI.)

---

## 3. Source material — files to read in CDSCO-RegAI

Source repo: `/home/atc/Desktop/cdcso/CDSCO-RegAI` — currently on `main`, all merged through PR #3. Read these files **first** to understand the design before writing any new code:

| CDSCO-RegAI path | What it does | Where it goes in biltiq-privacy |
|---|---|---|
| `backend/utils/pii_patterns.py` | Residual-scan regex set (Aadhaar/PAN/phone/email/ABHA) — single source of truth | `biltiq_privacy/core/pii_patterns.py` |
| `backend/utils/log.py` | `_RedactionFilter` (logging.Filter subclass) — scrubs PII from `record.msg`, `record.args`, `extra=` fields | `biltiq_privacy/core/log_filter.py` |
| `backend/utils/doc_hasher.py` | `hmac_pseudonymise()` helper using `settings.HMAC_KEY` | `biltiq_privacy/core/doc_hasher.py` (refactor: take key as constructor arg, no global settings) |
| `backend/modules/anonymisation/presidio_engine.py` | 7 Indian `PatternRecognizer`s (Aadhaar, PAN, ABHA, GSTIN, Voter ID, IFSC, phone) | `biltiq_privacy/recognisers/india.py` |
| `backend/modules/anonymisation/pseudonymiser.py` | `pseudonymise_text()` — replaces detected PII with deterministic HMAC tokens | `biltiq_privacy/core/pseudonymiser.py` |
| `backend/modules/anonymisation/generaliser.py` | 20-year age brackets + state→region rollup (k-anonymity) | `biltiq_privacy/core/generaliser.py` |
| `backend/modules/anonymisation/contextual_detector.py` | LLM-based contextual PII detection | `biltiq_privacy/detectors/llm_backend.py` (refactor: take an OpenAI-compatible client as arg, no hardcoded vLLM URLs) |
| `backend/modules/anonymisation/pipeline.py` | Orchestrator — runs detection → pseudonymisation → generalisation | `biltiq_privacy/detectors/hybrid.py` (refactor: drop FastAPI deps, return plain dicts) |
| `backend/compliance/dpdp_validator.py` | 8-check DPDP/NDHM/ICMR validator | `biltiq_privacy/regimes/dpdp.py` |
| `backend/modules/audit.py` | `_hash_timeline_row()`, `append_timeline_event()`, `verify_case_chain()` — hash-chain audit | `biltiq_privacy/core/audit_chain.py` (refactor: extract pure hashing logic; let consumers handle persistence) |

**Refactoring discipline:** the CDSCO-RegAI versions have FastAPI / SQLAlchemy / pydantic-settings glue baked in. The library equivalents must have **no framework dependencies**. Take secrets and config as constructor arguments. Return plain dicts / dataclasses. Let consumers wire it into their persistence layer.

---

## 4. Target directory layout

```
biltiq-privacy/
├── pyproject.toml              # build-system: hatchling. deps: presidio-analyzer, presidio-anonymizer
├── README.md                   # quickstart + per-regime examples
├── LICENSE                     # MIT
├── CHANGELOG.md                # starts at 0.1.0
├── docs/
│   ├── architecture.md
│   ├── regimes/dpdp.md
│   ├── regimes/gdpr.md
│   └── regimes/hipaa.md
├── biltiq_privacy/
│   ├── __init__.py             # public API: re-exports
│   ├── core/
│   │   ├── pseudonymiser.py
│   │   ├── generaliser.py
│   │   ├── pii_patterns.py
│   │   ├── log_filter.py
│   │   ├── audit_chain.py
│   │   └── doc_hasher.py
│   ├── recognisers/
│   │   ├── __init__.py         # convenience: build_engine(regions=['india', 'eu'])
│   │   ├── india.py            # v0.1.0
│   │   ├── eu.py               # v0.2.0
│   │   ├── us.py               # v0.3.0
│   │   └── uk.py               # v0.3.0
│   ├── detectors/
│   │   ├── base.py             # Detector ABC
│   │   ├── presidio_backend.py # default
│   │   ├── llm_backend.py      # v0.4.0
│   │   └── hybrid.py           # v0.4.0
│   ├── regimes/
│   │   ├── base.py             # Regime ABC: validate() -> ComplianceReport
│   │   ├── dpdp.py             # v0.1.0
│   │   ├── gdpr.py             # v0.2.0
│   │   ├── hipaa.py            # v0.3.0
│   │   └── ccpa.py             # v0.3.0
│   ├── backup/
│   │   ├── age_pipeline.py     # v0.5.0 — wraps `age` binary via subprocess
│   │   └── manifest.py         # v0.5.0 — HMAC-signed MANIFEST.json
│   └── cli.py                  # `biltiq-privacy scan <file>`, `... validate <regime>`
├── tests/
│   ├── conftest.py
│   ├── core/test_pseudonymiser.py
│   ├── core/test_generaliser.py
│   ├── core/test_pii_patterns.py
│   ├── core/test_log_filter.py
│   ├── core/test_audit_chain.py
│   ├── recognisers/test_india.py
│   ├── detectors/test_presidio_backend.py
│   └── regimes/test_dpdp.py
├── scripts/
│   └── install-age.sh          # apt / brew / dnf detection + install
└── .github/
    └── workflows/
        ├── ci.yml              # pytest + mypy + ruff on py 3.11, 3.12, 3.13
        └── release.yml         # tag → PyPI publish (when ready)
```

---

## 5. The Regime adapter pattern (the differentiator)

This is what Presidio itself doesn't ship — *attestation against a regulatory framework*. Pattern:

```python
# biltiq_privacy/regimes/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ComplianceCheck:
    id: str               # e.g. "DPDP-1", "GDPR-Art17", "HIPAA-§164.514"
    name: str
    status: str           # "pass" | "fail" | "warning" | "info"
    details: str
    section: str          # legal reference

@dataclass
class ComplianceReport:
    regime: str
    compliant: bool
    score: str            # "8/8"
    checks: list[ComplianceCheck]
    timestamp: str

class Regime(ABC):
    @abstractmethod
    def validate(
        self,
        *,
        original_text: str,
        anonymised_text: str,
        detections: list[dict],
        audit_records: list[dict],
    ) -> ComplianceReport: ...
```

Then `regimes/dpdp.py` (port from CDSCO-RegAI's 8 checks), `regimes/gdpr.py`, `regimes/hipaa.py` each implement that interface. Consumer:

```python
from biltiq_privacy.regimes import DPDP, GDPR, HIPAA

reports = [r.validate(...) for r in (DPDP(), GDPR(), HIPAA())]
# multi-regime attestation in one call
```

---

## 6. v0.1.0 scope (first milestone)

Ship exactly this and no more:

- `core/pii_patterns.py`, `core/log_filter.py`, `core/pseudonymiser.py`, `core/generaliser.py`, `core/doc_hasher.py`, `core/audit_chain.py`
- `recognisers/india.py` (the 7 Indian recognisers)
- `regimes/base.py` + `regimes/dpdp.py`
- `detectors/base.py` + `detectors/presidio_backend.py`
- Tests for everything (>= 90% coverage on `core/` and `recognisers/`)
- `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`
- CI: pytest + mypy --strict + ruff on Python 3.11 / 3.12 / 3.13

No CLI yet. No backup module yet. No GDPR/HIPAA yet. **Ship narrow, iterate.**

## 7. Future milestones (rough)

- **v0.2.0:** `regimes/gdpr.py` + `recognisers/eu.py` (IBAN, German Steuer-ID, French NIR, UK NHS number, etc.)
- **v0.3.0:** `regimes/hipaa.py` + `regimes/ccpa.py` + `recognisers/us.py` (SSN, EIN, MRN, driver's licence)
- **v0.4.0:** `detectors/llm_backend.py` + `detectors/hybrid.py` (port contextual detector, model-agnostic)
- **v0.5.0:** `backup/age_pipeline.py` + `backup/manifest.py` (port the BILTIQ-002 work from CDSCO-RegAI)
- **v1.0.0:** API freeze, semver enforcement, public PyPI release

---

## 8. Quality bars (must-pass before any version tag)

- `pytest` green on Python 3.11, 3.12, 3.13
- `mypy --strict` green (no `Any`, no untyped defs)
- `ruff format` + `ruff check --select=E,F,I,B,UP` green
- Pre-commit hooks installed and green
- Test coverage ≥ 90% on `core/` and `recognisers/`
- No banned vocabulary anywhere in the repo
- README has a runnable quickstart example

---

## 9. Hand-off decisions to confirm with the user before coding

Ask these in the first message of the new session:

1. **Python version range** — recommend 3.11 → 3.13. Confirm?
2. **PyPI release plan** — public PyPI from day one, or private/internal-only for v0.1.0?
3. **Versioning start** — v0.1.0 (signals alpha) or v1.0.0 (signals API stability)? Recommend 0.1.0.
4. **spaCy model dependency** — Presidio defaults to `en_core_web_sm`. Bundle, or require consumer to install? Recommend require.
5. **HMAC key management** — accept key as constructor arg (no global state), confirm.
6. **`age` binary** — system dep only, or also offer a `biltiq-privacy[backup]` extra that bundles a Go-built static binary? Recommend system dep only for v0.1.0.

---

## 10. Where this brief lives

- This file: `/home/atc/Desktop/biltiq-privacy/SESSION_PROMPT.md`
- Source repo to read from: `/home/atc/Desktop/cdcso/CDSCO-RegAI` (branch: `main`)
- Target repo (does not exist on GitHub yet — the new session creates it): `github.com/atcuality2021/biltiq-privacy`

## 11. First action for the new session

1. Read the 10 source files listed in §3 (in order).
2. Read this brief in full.
3. Ask the 6 hand-off questions in §9 — get answers before any code.
4. Set up `pyproject.toml` + skeleton directories (no implementation yet) — commit as `chore: initial skeleton`.
5. Implement `core/` first (pure functions, no deps), with tests alongside each module.
6. Then `recognisers/india.py`, then `regimes/dpdp.py`, then `detectors/presidio_backend.py`.
7. Ship v0.1.0 when §6 scope is complete and §8 bars are green.

Good luck.
