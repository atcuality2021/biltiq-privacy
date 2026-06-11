# Competitive Roadmap — Skyflow Parity + Beyond

**Purpose:** Skyflow (skyflow.com) is the category leader for the "data privacy vault" and a future competitor for biltiq-privacy. This document inventories every Skyflow capability, maps each to a BiltIQ ticket (existing or new), and states the **improvement** — where we must not merely match but beat them. Reviewed alongside `overview.md`; tickets graduate to `docs/specs/<id>/spec.html` when scheduled.

**Date:** 2026-06-11 · **Source analysis:** session gap-analysis vs skyflow.com + docs.skyflow.com (product pages: PII vault, Detect, GenAI/Agents, Payments, Healthcare, Data Residency, Governance, Connections).

---

## Architectural stance (decided — do not relitigate per ticket)

Skyflow is a **SaaS vault**: sensitive data leaves the customer's stack and lives in Skyflow's isolated store; apps hold tokens and call APIs. biltiq-privacy is an **embeddable engine**: data never leaves the consumer's process/network; we ship the primitives, consumers own persistence and keys.

We do NOT build a hosted multi-tenant vault. Every parity item below is delivered **vault-less**: same capability, consumer-held keys, consumer-owned storage, fully on-prem. That inversion *is* the improvement for our buyers (Indian healthcare/BFSI/government, sovereign and air-gapped deployments, anyone Skyflow's enterprise SaaS pricing or data-egress model excludes).

Standing advantages to preserve in every ticket: MIT licence + auditable source · `pip install` adoption (minutes, not sales cycles) · deterministic, golden-vector-pinned primitives · tamper-evident audit chain (cryptographic, not just logs) · typed `ComplianceReport` attestation (they claim compliance; we *emit evidence*) · Indian-PII depth (Aadhaar/ABHA/GSTIN/IFSC/Voter ID/Medical Reg vs their generic DPDP checkbox).

---

## Capability map — Skyflow feature → BiltIQ ticket → our improvement

### Already shipped (parity or better today)

| Skyflow capability | Ours | Status |
|---|---|---|
| Detect API (text) | `Detector` ABC + `PresidioDetector` + 8 Indian recognisers (BILTIQ-002/009) | **Better for India**; breadth gap closed by BILTIQ-026 + EU/US/UK packs (v0.2.0) |
| Masking/redaction | `redact()`, generaliser rollups (BILTIQ-002/008) | Parity |
| De-identification (one-way) | HMAC `Pseudonymiser` (BILTIQ-007) | Parity for one-way; reversibility is BILTIQ-014 |
| Audit logging | **Tamper-evident hash chain** + golden vector (BILTIQ-010) | **Better** — cryptographic evidence vs platform logs |
| Compliance posture | **`ComplianceReport`** per-check attestation, DPDP first (BILTIQ-011) | **Better** — machine-readable, regulator-grade artifact; GDPR/HIPAA/CCPA = BILTIQ-017/018/019 |
| Data residency | Inherent: the engine runs in situ; data never crosses a boundary | **Better by architecture** — document as a marketing/positioning page, no code needed |

### Scheduled (already on the roadmap, unchanged)

| Skyflow capability | Ours | Ticket |
|---|---|---|
| One-call privacy API | `anonymise()` orchestration facade | **BILTIQ-012** (next up) |
| Data/Detect REST APIs | FastAPI sidecar `/anonymize`, `/validate` | **BILTIQ-013** |
| Multi-language SDKs | Node/PHP/Go thin SDKs over the sidecar, golden-vector-verified | v0.1.1+ (existing plan) |
| GDPR/HIPAA/CCPA | Regime adapters behind the BILTIQ-011 ABC | **BILTIQ-017/018/019** (Phase C) |
| Broader entity coverage | EU/US/UK recogniser packs + multi-region `build_engine(regions=[...])` | v0.2.0 (existing plan) |
| Anonymisation strength metrics | k-anonymity measurement | **BILTIQ-021** |

### New tickets (this document's output)

---

#### BILTIQ-014 — Reversible pseudonymisation (vault-less detokenize) · v0.2.0 · HIGH PRIORITY

**Skyflow feature matched:** vault tokenization + authorised detokenize / GenAI re-identification.

**Scope:**
- `core.token_map.TokenMap` — encrypted token→value mapping the **consumer persists** (we never store it): entries sealed with a consumer-held key (AES-GCM via `cryptography`, or the age wrapper for file-level seals — design decision), keyed by the existing deterministic HMAC token.
- `Pseudonymiser` gains an opt-in `token_map=` seam: when supplied, `pseudonymise_text` records sealed originals; without it, behaviour is today's one-way (default unchanged).
- `reidentify(text_or_tokens, *, token_map, key, scope=None) -> str` — restores originals; `scope` restricts which entity types may be re-identified (the authz seam BILTIQ-020 policies will drive).
- Every re-identification emits an `AuditRecord`-shaped event suitable for the hash chain — **re-identification is itself an auditable disclosure**.
- DPDP-3 (reversibility check) gains a true backing capability instead of token-shape inference.

**Draft ACs:** (1) round-trip: pseudonymise→reidentify restores byte-identical originals; (2) without the key or map, re-identification is computationally infeasible (HMAC remains one-way); (3) scope filter enforced — out-of-scope entity types stay tokenised; (4) map format versioned + documented for cross-language SDKs (golden vector); (5) default path (no map) byte-identical to BILTIQ-007 behaviour; (6) re-identification events chain-appendable.

**Better than Skyflow:** detokenization without surrendering data custody — the map and key never leave the consumer; no vendor can be subpoenaed, breached, or priced into the read path. Plus disclosure-grade audit on every re-identification, which their detokenize logs don't cryptographically prove.

**Risk:** key management UX; mitigated by runbook + sane `cryptography` defaults. HIGH-RISK ticket (crypto + compliance) → mandatory human plan review.

---

#### BILTIQ-015 — LLM & agent privacy facade + sensitive-terms dictionary · v0.2.0 · HIGH PRIORITY

**Skyflow feature matched:** LLM Privacy Vault / GenAI product (de-identify for training/RAG/inference, re-identify responses, sensitive-data dictionary, agent data control).

**Scope:**
- `llm.PrivacyGate` — wraps any OpenAI-compatible client (vLLM first-class): `protect(prompt) -> (safe_prompt, session_map)`, `restore(response, session_map) -> str`. Composes detect → pseudonymise (BILTIQ-014 map for the restore leg) → optional generalise.
- `detectors.dictionary.DictionaryDetector(terms=...)` — exact/normalised match over consumer-defined sensitive terms (project codenames, drug names, client names — their "sensitive data dictionary") behind the existing `Detector` ABC; composes with `PresidioDetector` via a simple `CompositeDetector`.
- Pipeline-stage guidance docs: collection / fine-tuning / RAG indexing / inference — each a documented recipe over the same primitives, not new code paths.
- Per-call audit rows (prompt protected, entities found, response restored) → hash chain.

**Draft ACs:** (1) protect→LLM→restore round-trip preserves non-PII text and restores PII only via the session map; (2) dictionary terms detected with configurable normalisation (case/whitespace), zero Presidio dependency; (3) composite detection dedupes overlapping spans deterministically; (4) no network calls inside the library — the consumer's client object makes the LLM call; (5) works against a live vLLM endpoint in an integration test (CI-skippable); (6) audit rows chain-verifiable.

**Better than Skyflow:** their GenAI story still routes data through their SaaS; ours runs entirely inside the consumer's GPU estate (vLLM-native — exactly the BiltIQ deployment model). Dictionary + regex + NER compose under one ABC instead of separate products. `on_prem_required` projects can use it; they can't use Skyflow at all.

---

#### BILTIQ-016 — Unstructured-data detection: files, images, audio · v0.3.0

**Skyflow feature matched:** Detect for "text, audio, images, and files".

**Scope (three phases, one spec):**
- P1 — file text extraction seam: `extractors.Extractor` ABC + PDF/DOCX/TXT/HTML backends (pypdf, python-docx — stdlib-adjacent, no service); extracted text flows into the existing `Detector` path with span→page/offset mapping for redaction output.
- P2 — images: OCR backend behind the same ABC (Tesseract local default; consumer-supplied vision-LLM client optional per compliance mode + ADR).
- P3 — audio: ASR seam (consumer-supplied client, e.g. their on-prem ATC Voice/whisper endpoint) → transcript → text path; we ship the seam + redaction-timeline mapping, not a bundled model.
- Redacted-artifact writers: text overlay for PDFs (P1), boxed-region image redaction (P2).

**Draft ACs:** extraction fidelity fixtures per format; span provenance (file/page/offset) on every `DetectedEntity`; no model bundled beyond Tesseract optionality; lazy imports throughout (the BILTIQ-009 discipline).

**Better than Skyflow:** pluggable on-prem OCR/ASR — consumers point at their own models (BiltIQ GPU nodes, whisper, anything OpenAI-compatible) instead of shipping audio/images to a US SaaS. For hospitals, scanned-form redaction that never leaves the building is the entire sale.

---

#### BILTIQ-020 — Sidecar governance: policies, roles, scoped keys · v0.3.0 (extends BILTIQ-013)

**Skyflow feature matched:** Governance (roles, policies, service accounts, field-level access).

**Scope:**
- Declarative policy file (YAML/JSON, pydantic-validated, hot-reloadable): principals (API keys/service accounts) → allowed operations (`anonymise`, `validate`, `reidentify`) → entity-type scopes → regime constraints.
- Per-principal rate limits + per-operation audit emission to the hash chain (governance decisions are themselves chained evidence).
- `reidentify` endpoint (BILTIQ-014 over HTTP) is **deny-by-default** — exposed only via explicit policy; `include_values` never exposed over HTTP (standing decision from BILTIQ-011).
- Library stays pure: all governance lives in `python-server`.

**Better than Skyflow:** policy-as-code in git (reviewable, diffable, CI-testable) vs console-configured policies; every allow/deny decision lands in the tamper-evident chain, so governance is *provable* after the fact.

---

#### BILTIQ-023 — Egress connections (tokenised pass-through proxy) · v0.4.0

**Skyflow feature matched:** Connections (tokens flow to Stripe/Plaid/VISA without the app touching raw values).

**Scope:** sidecar route that accepts a request template containing tokens, re-identifies *inside the sidecar* under BILTIQ-020 policy, forwards to an allow-listed downstream URL, and returns the response with any echoed PII re-tokenised. Allow-list is policy-file-driven; every egress is chained.

**Better than Skyflow:** the proxy runs in the consumer's network — raw values exist only in transit between *their* sidecar and *their* contracted downstream; we never see them. Compliance-mode aware: `on_prem_required` projects can restrict the allow-list to intranet hosts.

**Honest note:** this is the parity item with real engineering weight (streaming, retries, response transformation). Schedule only after BILTIQ-013/014/020 are stable.

---

#### BILTIQ-024 — Field-level envelope encryption + queryable protection · v0.5.0 (extends the existing encryption phase)

**Skyflow feature matched:** "polymorphic encryption" — operate on data without decrypting.

**Scope:** per-field envelope encryption helpers (DEK/KEK, consumer KMS or age identities); **deterministic encryption mode** for equality-searchable fields (with documented leakage trade-offs); blind-index helpers (HMAC-based, reusing doc_hasher) for lookup-without-decrypt. Explicitly NOT homomorphic/order-preserving claims — we publish the leakage profile of each mode instead of a patented black box.

**Better than Skyflow:** documented, auditable cryptography with stated trade-offs vs marketing-grade "polymorphic" opacity; keys in the consumer's KMS, full stop.

---

#### BILTIQ-025 — MCP server + agent runtime guard · v0.3.0

**Skyflow feature matched:** their MCP server + "Agents & AI Security" runtime data control.

**Scope:** `biltiq-privacy-mcp` exposing `anonymise`, `detect`, `validate_regime`, (policy-gated) `reidentify` as MCP tools over the sidecar — agents and AI IDEs get privacy operations natively. Plus a documented "tool-output guard" recipe: wrap any MCP tool so its output passes through `PrivacyGate` before reaching the model.

**Better than Skyflow:** the guard composes with *any* MCP server (it's a library wrapper, not a platform feature), and runs air-gapped.

---

#### BILTIQ-026 — Custom recogniser registry + pack SDK · v0.2.0

**Skyflow feature matched:** customer-defined sensitive data types (their dictionary, generalised).

**Scope:** declarative recogniser packs (YAML/JSON: name, regex or term-list, score, language) loadable at runtime — `build_engine(packs=[...])`; validation + collision rules vs built-in entity types; the BILTIQ-015 dictionary becomes one pack kind. Ships with the EU/US/UK pack work.

**Better than Skyflow:** packs are files in the consumer's repo — versioned, reviewed, tested with their fixtures; community packs become possible (MIT).

---

### Deliberately NOT built (decided)

| Skyflow capability | Decision |
|---|---|
| Hosted multi-tenant vault / storage plane | Out of mission — the engine's vault-less architecture is the product. Revisit only with an ADR + business case. |
| Payments stack (card issuance, 3DS, network tokens, account updater, BIN lookup) | PCI-DSS service scope is a different business. BILTIQ-023's proxy + BILTIQ-024 encryption cover "protect card data in my own systems"; full payments rails are not on the roadmap. |
| SOC 2-style platform certifications | Not applicable to a library (no service to certify); the sidecar deployment guide documents what *consumers* need for their audits. No certification claims (CONTEXT.md rule). |

---

## Phasing summary

| Version | Tickets | Theme |
|---|---|---|
| v0.1.0 (now) | 011 merge, **012**, **013** | Close the core: attestation, facade, sidecar |
| v0.2.0 | **014**, **015**, **026**, EU/US/UK packs, 017–019 | Reversibility + LLM privacy + extensibility — the Skyflow head-to-head release |
| v0.3.0 | **016**, **020**, **025**, 021 | Unstructured data, governance, agents |
| v0.4.0 | **023**, LLM/hybrid detectors (existing plan) | Egress + contextual detection |
| v0.5.0 | **024** + existing envelope-encryption plan | Encryption depth |

Priority order if capacity forces a choice: **014 → 015 → 026 → 020 → 016 → 025 → 023 → 024.** (014/015 are what prospects will benchmark against Skyflow's demo.)

---

## Change history

| Date | What | Trigger |
|---|---|---|
| 2026-06-11 | Initial roadmap from Skyflow gap analysis; 8 new tickets scoped (014/015/016/020/023/024/025/026); spec scaffolds created for 014 + 015 | Competitive study session |
