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
