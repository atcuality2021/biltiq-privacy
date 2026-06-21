# Approved Versions & Deprecated APIs

**Purpose:** Anti-Pattern #9 defense. AI agents are trained on historical code and don't distinguish current from deprecated. This file is the source of truth for what is current and what is banned.

**Update rules:**
- When a dependency is upgraded across a major version, add a row.
- When an API method is deprecated upstream (or by us), add a row.
- The `code-reviewer` skill and the `biltiq-gates.yml` CI both consult this file. Keep it accurate.

---

## Currently approved (use these)

### Python

| API | Use | Notes |
|---|---|---|
| `datetime.now(timezone.utc)` | UTC timestamps | All timestamps in audit-chain rows. |
| `importlib.metadata` | Read package metadata | Replaces `pkg_resources`. |
| `asyncio.timeout` | Async timeouts (3.11+) | Replaces `asyncio.wait_for`. |
| `pathlib.Path` | Path manipulation | Prefer over `os.path`. |
| `@dataclass(slots=True, frozen=True)` | Return types from library | Default shape for `ComplianceCheck`, `ComplianceReport`, detector results. |
| `pydantic.BaseModel` v2 API | Server request/response models | `model_validate`, `model_dump` (not `.parse_obj` / `.dict`). **Pydantic is server-only; library uses dataclasses.** |
| `from __future__ import annotations` | Top of every module | Required. Enables forward refs and `mypy --strict`. |

### Presidio

| API | Use | Notes |
|---|---|---|
| `presidio_analyzer.AnalyzerEngine` | Default detection | Built via `recognisers.build_engine(regions=[...])`. |
| `presidio_analyzer.PatternRecognizer` | Adding regex recognisers | India / EU / US / UK PII packs subclass this. |
| `presidio_analyzer.EntityRecognizer` | Adding ML / contextual recognisers | `v0.4.0+` LLM backend. |
| `presidio_anonymizer.operators.Operator` | Custom pseudonymisation operators | HMAC-token operator lives here. |

### FastAPI (server package only)

| API | Use | Notes |
|---|---|---|
| `APIRouter` with route dependencies | Endpoint organisation + auth | One router per endpoint module; gate with `APIRouter(dependencies=[Depends(require_jwt)])` (BILTIQ-013). |
| `lifespan=` async context manager | App startup/shutdown | Build the detector once at boot (BILTIQ-013). **Approved replacement for `@app.on_event`** (deprecated below). |
| `Depends()` for HMAC-key resolution | Inject config | Reads env once at startup, passes per-request. The HMAC key reaches handlers only via `get_hmac_key` — never a body field (BILTIQ-013, AC6). |
| `BackgroundTasks` for audit log flush | Audit chain | Not on the request path. |
| `TestClient` for tests | Integration tests | No real network. |

### Auth (server package only)

| API | Use | Notes |
|---|---|---|
| `PyJWT ≥ 2.8, < 3` — `jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": True})` | Bearer-JWT verification | HS256, **verify-only** (ADR-0007). Pin a single-element `algorithms` allow-list — closes the algorithm-confusion class. Production never calls `jwt.encode` (consumers mint their own tokens); `auth.py` is the only `jwt` importer. PEP 561 typed. |

### System binaries

| Binary | Version | Use | Notes |
|---|---|---|---|
| `age` | ≥ 1.2.0 | X25519 + ChaCha20-Poly1305 streaming encryption for backup pipelines (v0.5.0+) | Wrapped via `biltiq_privacy.backup.age_stream` (BILTIQ-004). Pinned in `docs/architecture/stack.md` § Encryption and in `scripts/install-age.sh`'s `AGE_VERSION`. Install via `scripts/install-age.sh` (autodetect) or `docs/runbooks/install-age.md` (manual). See ADR-0003. |

### Database / persistence

**The library has no persistence layer.** Consumers wire `AuditChain` rows into whatever store they use (Postgres, SQLite, file). If you find yourself adding `sqlalchemy` or `psycopg` to `packages/python-core/`, stop and read `AGENT_RULES.md` § Library vs server boundary.

---

## Deprecated (do not use)

### Python

| Deprecated API | Replacement | Reason |
|---|---|---|
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Naive datetime, deprecated in 3.12. |
| `pkg_resources` | `importlib.metadata` | Slow, deprecated. |
| `imp` module | `importlib` | Removed in 3.12. |
| `distutils` | `setuptools` / `build` | Removed in 3.12. |
| `asyncio.coroutine` decorator | `async def` | Removed in 3.11. |
| `requests` (sync) | `httpx` (async) in the SDK helpers | Async-first stack. |
| Bare `except:` | Specific exception, or `except Exception:` with explicit propagation | Anti-Pattern #3. |
| `print()` in production code | `logging.getLogger(__name__).info()` (attach `RedactionFilter` once it ships — PLANNED, see stack.md) | No structured output, no PII redaction otherwise. |
| `python-Levenshtein` | `rapidfuzz` | GPL-2.0 contamination risk (Brief §2 rule 4). |
| `pymupdf` | (extract PDF in *consuming* projects, not in this lib) | AGPL-3.0 contamination risk (Brief §2 rule 4). |

### Pydantic v1 → v2 migration

| Deprecated v1 | Replacement v2 | Reason |
|---|---|---|
| `BaseModel.parse_obj(data)` | `BaseModel.model_validate(data)` | v1 API. |
| `BaseModel.dict()` | `BaseModel.model_dump()` | v1 API. |
| `BaseModel.json()` | `BaseModel.model_dump_json()` | v1 API. |
| `validator` decorator | `field_validator` / `model_validator` | v1 API. |

### FastAPI (server package only)

| Deprecated API | Replacement | Reason |
|---|---|---|
| `@app.on_event("startup")` / `@app.on_event("shutdown")` | `lifespan=` async context manager passed to `FastAPI(...)` | Deprecated upstream since Starlette 0.x; the `lifespan` form is the supported single-entry startup/shutdown hook (BILTIQ-013). |

### Presidio

| Deprecated | Replacement | Reason |
|---|---|---|
| Forking presidio-analyzer or presidio-anonymizer | Depend, pin (`>=2.2,<3`), layer via `PatternRecognizer` / `EntityRecognizer` | Brief §2 rule 1. Maintenance burden of a fork is multi-engineer-year scope. |
| Modifying vendored Presidio code | Wrap or subclass instead; if upstream gap is real, file an upstream issue | `vendor/presidio/` is a pinned mirror, not a fork. |

### Project-specific

| Deprecated | Replacement | Removal target |
|---|---|---|
| (none yet — repo is pre-implementation) | | |

---

## Hard dependency pins (project-specific)

These pins are deliberately tight because the library exposes specific Presidio APIs and a major version bump could change them:

```toml
# pyproject.toml (packages/python-core/)
[project.dependencies]
"presidio-analyzer >= 2.2, < 3"
"presidio-anonymizer >= 2.2, < 3"
"spacy >= 3.7, < 4"
"rapidfuzz >= 3.0, < 4"

# en-core-web-sm is dev-path-only since BILTIQ-012 (ADR-0006): PyPI rejects
# direct-URL Requires-Dist, so the published dist ships without the model.
# The pin lives in the repo-root [dependency-groups].dev, the package's own
# [dependency-groups].dev, and ci.yml's explicit install line;
# consumers post-install (`python -m spacy download en_core_web_sm`) or opt
# into PresidioDetector(auto_download_model=True). Version pin unchanged
# from ADR-0002 (3.8.0).
```

```toml
# pyproject.toml (packages/python-server/)
[project.dependencies]
"biltiq-privacy"   # same workspace version
"fastapi >= 0.110, < 1"
"uvicorn[standard] >= 0.27, < 1"
"pydantic >= 2.5, < 3"
```

When upgrading any of these across a major version, write an ADR and run the full test suite plus the integration tests against the 7 Indian recognisers' golden corpus.

### Transient resolver constraints (uv path only)

These constraints live in the root `pyproject.toml` under `[tool.uv] constraint-dependencies` and apply only to the `uv sync` install path. The pip path resolves independently and is not affected (pip's resolver auto-backtracks across the same wheel gaps that trip uv).

| Date | Constraint | Reason | Remove when |
|------|------------|--------|-------------|
| 2026-05-17 | `spacy<3.8.14` | spaCy 3.8.14 (latest release as of 2026-05-17) lacks cp314 wheels; uv refuses to backtrack, pip backtracks to 3.8.13 automatically. Constraint pins uv to 3.8.13 on all Pythons; pip-on-3.14 lands on 3.8.13 naturally; pip on 3.11/3.12/3.13 may pick 3.8.13 or 3.8.14. | Explosion publishes cp314 wheels for the next spaCy release (≥ 3.8.14 with cp314 wheel) — verify by running `uv sync --python 3.14` without the constraint; if no resolver error, drop the line. |

---

## How this file is enforced

- The `code-reviewer` skill greps the diff against the deprecated patterns.
- The `anti-pattern-scanner` skill includes these in its #9 (Deprecated APIs) section.
- CI (`.github/workflows/biltiq-gates.yml`) runs lint rules that block known-deprecated calls — `ruff` rules `DTZ`, `UP`, `B`, plus project-specific custom rules.
- Pre-commit hook (`.pre-commit-config.yaml`) catches the most common ones locally before they reach CI.

If you find an API in production code that is on the deprecated list, the fix is a separate task with its own spec — don't bundle removal into an unrelated PR.
