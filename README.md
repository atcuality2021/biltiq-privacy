# biltiq-privacy

A reusable Python library + FastAPI sidecar + thin native SDKs for PII detection, pseudonymisation, and region-specific compliance checks (DPDP, GDPR, HIPAA, CCPA). Layered on top of Microsoft Presidio; productised from CDSCO-RegAI's production stack. MIT-licensed, shipped to public PyPI from v0.1.0 (alpha).

> **Status:** v0.1.0 (alpha) — the core pipeline is complete: Indian PII detection, HMAC pseudonymisation, rule-based generalisation, the DPDP 2023 validator, a tamper-evident audit hash-chain, and the `anonymise()` facade tying them together. Sidecar + native SDKs land in v0.1.1+. Track progress at [`docs/specs/`](docs/specs/).

## Usage

```bash
pip install biltiq-privacy
python -m spacy download en_core_web_sm   # NER model — one-time post-install (ADR-0006)
```

```python
from biltiq_privacy import DPDPRegime, PresidioDetector, anonymise, verify_chain

result = anonymise(
    "Patient Aadhaar 1234 5678 9011; mobile 9876543210.",
    detector=PresidioDetector(),     # or PresidioDetector(auto_download_model=True)
    key=b"your-32-byte-secret-key-here....",   # HMAC key — injected, never read from env
    generated_at="2026-06-11T00:00:00+00:00",  # caller-supplied; the library reads no clock
    regime=DPDPRegime(),                       # optional compliance attestation
)

print(result.anonymised_text)        # tokens + generalisations; originals gone
print(result.compliance.score)      # e.g. "8/8" — DPDP 2023 check results
assert verify_chain([result.audit_row])["valid"]

# Chain the next document onto the same tamper-evident audit trail:
next_result = anonymise(
    "Follow-up note.",
    detector=PresidioDetector(),
    key=b"your-32-byte-secret-key-here....",
    generated_at="2026-06-11T00:05:00+00:00",
    prev_hash=result.audit_row["hash"],
)
assert verify_chain([result.audit_row, next_result.audit_row])["valid"]
```

`result.detections` carries the original span text by design (the detector contract) — treat the result object as sensitive and don't log it raw. The audit-chain payload itself is PII-free (counts, flags, and SHA-256 commitments only), so the rows are safe to persist anywhere.

## Who it's for

Python applications that need:

- PII detection across India / EU / US / UK recognisers.
- Pseudonymisation, generalisation, or HMAC-token anonymisation operators.
- Region-specific compliance validators (DPDP 2023 India, GDPR, HIPAA, CCPA) layered on Presidio's detection.
- A hash-chain audit primitive that the consumer wires into their own persistence layer.

Two integration modes — both first-class:

- **Library mode** — `pip install biltiq-privacy`. Framework-free. No web stack pulled in. Suits on-prem and airgapped deployments where the consumer wants the engine in-process.
- **Sidecar mode** — `pip install biltiq-privacy-server && uvicorn biltiq_privacy_server.app:app` (native, ~120 MB RAM) or the published `biltiq/privacy-server:0.1.0` Docker image (~350 MB RAM). REST endpoints `/anonymize` and `/validate`. Thin SDKs in Node, PHP, Go wrap the sidecar.

The default deployment story is **native pip + systemd**; the Docker image is offered, not led with.

## Quick start

### Path 1 — pip (canonical, no extra toolchain)

```bash
pip install -e packages/python-core \
            -e packages/python-server \
            -e .
pytest
```

Three editable installs in one command. pip resolves the sibling packages from the local checkouts before reaching for PyPI, so the workspace is fully editable without publishing v0.1.0.

### Path 2 — uv (opt-in, faster, lockfile-aware)

```bash
uv sync
uv run pytest
```

`[tool.uv.workspace]` in the root `pyproject.toml` declares both packages as members and `[tool.uv.sources]` pins them to the local workspace. The committed `uv.lock` gives reproducible installs.

Both paths run the same 4-Python matrix (3.11 / 3.12 / 3.13 / 3.14) and the same tests.

## Sidecar (REST server)

The `biltiq-privacy-server` package wraps the engine in a FastAPI sidecar — for the Node / PHP / Go SDKs and any non-Python consumer.

```bash
pip install biltiq-privacy-server
python -m spacy download en_core_web_sm   # NER model — one-time post-install (ADR-0006)
```

The server reads two secrets from the environment at startup and **fails fast** if either is missing (the HMAC key must be ≥ 32 bytes). They are never logged and never travel over the wire:

```bash
export BILTIQ_JWT_SECRET='your-jwt-signing-secret'          # HS256 verification secret
export BILTIQ_HMAC_KEY='your-32-byte-pseudonymisation-key!' # ≥ 32 bytes (256-bit)
biltiq-privacy-server serve                                 # binds 0.0.0.0:8088, 1 worker
# serve --host 127.0.0.1 --port 9090 --workers 4   # scale-out re-imports the app per worker
```

The data endpoints are **Bearer-JWT gated**. The server is **verify-only** — it never issues tokens; **consumers mint their own JWT** signed with `BILTIQ_JWT_SECRET` (ADR-0007). For example, in Python:

```python
import jwt, datetime  # PyJWT
token = jwt.encode(
    {"sub": "my-service", "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5)},
    "your-jwt-signing-secret",
    algorithm="HS256",
)
```

For operators and CI smoke tests, the `biltiq-privacy-mint` helper does the same correctly — the signing secret is read **only** from `BILTIQ_JWT_SECRET` (never a CLI argument, so it stays out of `ps` / shell history) and the token is the only thing printed:

```bash
TOKEN=$(BILTIQ_JWT_SECRET="your-jwt-signing-secret" biltiq-privacy-mint --sub ops --ttl 3600)
# extra claims (minted but not enforced by the verify-only server): --claim role=admin
```

This is an operator convenience, not a new server surface — the running server stays **verify-only** and never issues tokens (the mint is a separate console-script; `jwt.encode` lives only there, unreachable from the server's request path — ADR-0007).

One call per endpoint (`$TOKEN` is the value above):

```bash
# Liveness/readiness — unauthenticated; 200 healthy, 503 if the NER model is missing
curl -s http://localhost:8088/healthz

# Detect PII spans
curl -s -X POST http://localhost:8088/detect \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Call Ravi on 9876543210."}'

# Anonymise (+ optional DPDP-2023 compliance attestation)
curl -s -X POST http://localhost:8088/anonymize \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Call Ravi on 9876543210.", "regime": "DPDP-2023"}'

# Validate an already-anonymised payload against a regime (fields come from an /anonymize response)
curl -s -X POST http://localhost:8088/validate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"original_text": "Call Ravi on 9876543210.",
       "anonymised_text": "Call Ravi on [IN_PHONE_8ea4f7ab].",
       "detections": [{"entity_type": "IN_PHONE", "text": "9876543210", "start": 13, "end": 23, "score": 0.9, "source": "presidio"}],
       "audit_records": [{"entity_type": "IN_PHONE", "pseudonym_token": "[IN_PHONE_8ea4f7ab]", "position_start": 13, "position_end": 23, "confidence": 0.9}],
       "regime": "DPDP-2023"}'
```

The HMAC pseudonymisation key never appears in a request or response — it is injected server-side per request, so SDK clients send only `text` and never handle the key.

### OpenAPI contract

`packages/python-server/openapi.json` is committed and is the contract the native SDK generator consumes. A drift test fails CI if the live schema and the committed file diverge. Regenerate it (no extra script — a one-liner) after any handler or model change:

```bash
python -c "import json; from biltiq_privacy_server import __version__; from biltiq_privacy_server.app import create_app; from biltiq_privacy_server.config import Settings; json.dump(create_app(Settings(jwt_secret='openapi-export', hmac_key=b'0'*32, version=__version__)).openapi(), open('packages/python-server/openapi.json','w'), indent=2, sort_keys=True); open('packages/python-server/openapi.json','a').write(chr(10))"
```

### Docker (offered, not led with)

A `packages/python-server/Dockerfile` scaffold builds from the repo root (`docker build -f packages/python-server/Dockerfile -t biltiq/privacy-server:0.1.0 .`). The default deployment is native pip + systemd; the image is a starting point — pin the base digest and add a non-root user before production.

## Repository layout

```
packages/
  python-core/           # biltiq-privacy        — the engine (framework-free)
  python-server/         # biltiq-privacy-server — the FastAPI sidecar
  node/                  # thin HTTP SDK (v0.1.1+)
  php/                   # thin HTTP SDK (v0.1.1+)
  go/                    # thin HTTP SDK (v0.1.1+)
pyproject.toml           # repo-root metapackage; wires both install paths
scripts/                 # check-boundaries.sh, others
.github/workflows/       # ci.yml (matrix + boundary-check), biltiq-gates.yml
docs/                    # architecture/, specs/, adr/, GLOSSARY.md
```

`packages/python-core/` MUST NOT import FastAPI, Starlette, or uvicorn — the library has to stay installable in airgapped, regulated, on-prem environments without dragging in a web stack. `scripts/check-boundaries.sh` enforces this; CI runs it on every PR.

## Architecture

See [`docs/architecture/overview.md`](docs/architecture/overview.md) for the system shape and [`docs/architecture/stack.md`](docs/architecture/stack.md) for the library set.

## Compliance mode

This repo runs at `on_prem_preferred` — declared in [`AGENT_RULES.md`](AGENT_RULES.md) § Compliance. The library itself performs no external AI or cloud API calls; the optional LLM detector (v0.4.0+) accepts a consumer-supplied OpenAI-compatible client.

## License

MIT — see [`LICENSE`](LICENSE). Hard rule: no AGPL / GPL transitive dependencies. `python-Levenshtein` and `pymupdf` are explicitly out (see `AGENT_RULES.md`).

## More documentation

[`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) is the doc index. The Attack Loop workflow lives in [`docs/specs/`](docs/specs/).
