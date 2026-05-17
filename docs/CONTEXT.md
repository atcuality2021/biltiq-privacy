# /docs/CONTEXT.md — Company & Product Context

**Purpose:** Background context the AI agent needs for any task involving documentation, marketing, communications, strategy, or anything user-facing. Read alongside `MEMORY.md` for any task that's not pure code.

---

## Who we are

**BiltIQ AI** (legal entity: Aarna Tech Consultants Private Limited) is a DPIIT-recognised startup and NVIDIA Inception Partner based in Jamshedpur, Jharkhand, India. We build agentic AI systems across deployment models — on-premise for regulated / sovereign-data work, cloud-native for non-regulated products and internal tools, and hybrid where the contract calls for it. Compliance posture is **declared per project** in `AGENT_RULES.md` § Compliance, not assumed by default.

**Positioning lines** (used in marketing for the on-premise category specifically): "Your Data. Your Premises. Your AI." For non-regulated cloud work, frame around capability and cost — not data sovereignty.

[PROJECT: customize below — not every BiltIQ repo is about a regulated-sector product.]

**This repo (biltiq-privacy) is a reusable Python library + FastAPI sidecar + native SDKs**, not a service deployed at a client site. It's published to public PyPI under MIT license, with a Docker image on Docker Hub / GHCR. Consumers (CDSCO-RegAI, ATC CommandCenter, ManthanQuant, plus future BiltIQ products) bundle the library or call the sidecar over HTTP. The company-level context below is background; this repo's own architecture lives in `/docs/architecture/overview.md`.

---

## What we make (the ATC product suite)

All products carry the **ATC** prefix. Never drop or modify it.

- **ATC Manthan** — Document AI / RAG
- **ATC Quest** — AI-native LMS (paying customers, TRL 8)
- **ATC Campus** — Edge AI for schools
- **ATC Chat** — Conversational AI with RAG + MCP
- **ATC Voice** — ASR / TTS / speech intelligence
- **ATC Flow** — Workflow automation
- **ATC CommandCenter** — AI-native CRM
- **ATC Connect**, **ATC Social**, **ATC CMS**, **ATC Ops** — supporting suite

**In development:**
- **Sehat Saathi** — WhatsApp-native health companion (TRL 5)
- **ATC HealthBridge** — B2G FHIR R4 infrastructure for NHA
- **CDSCO RegAI** — regulatory AI platform

---

## What we explicitly do NOT do (default — overridden by per-project compliance mode)

These defaults apply unless the repo's `AGENT_RULES.md` § Compliance declares otherwise:

- Do not deploy on public cloud for production workloads of regulated-sector products.
- Do not call external AI APIs in production paths of `on_prem_required` projects.
- Do not list cloud AI models as components in product specs of `on_prem_required` projects.
- Do not claim certifications we don't hold (no SOC 2, ISO 27001, HIPAA/GDPR/FedRAMP claims unless audited).
- Do not use stock photography in BiltIQ assets.
- Do not use marketing hyperbole — banned vocabulary list is in `AGENT_RULES.md`.

For `on_prem_preferred` and `cloud_ok` projects, cloud AI use is allowed per the compliance mode rules.

---

## Who we serve

Regulated sectors (default `on_prem_required` or `on_prem_preferred`):
- **Healthcare** — hospitals, clinics, pharmacy chains, B2G health (NHA, CDSCO)
- **Education** — schools, colleges, training institutes
- **BFSI** — banks, NBFCs, insurance
- **Manufacturing** — SMB and enterprise
- **Government** — state and central, including defence (active iDEX, ADITI, DRISHTI bids)

Non-regulated and internal-tools projects (often `cloud_ok` or `on_prem_preferred`):
- Internal automation tools.
- Prototypes and spikes.
- Client-approved cloud deployments.

If a task involves drafting customer-facing material, default tone is direct, technical, evidence-led.

---

## Infrastructure context

**GPU nodes (internal — addresses redacted for public repo):**
- Node 1: multimodal / vision LLM
- Node 2: ASR + vision-language embeddings + small medical / vision LLMs
- Node 3: primary reasoning LLM (large MoE)
- Node 4: ATC-System app node — FastAPI + PostgreSQL + pgvector + Qdrant + Redis + MinIO + Docker; training/fine-tuning capable

**Stack:** vLLM (OpenAI-compatible local endpoints), FastAPI, PostgreSQL, Qdrant, MinIO, Redis, Celery, MCP. Containerised with Docker Compose.

**Active safety flag:** an uncensored model variant is hosted internally for research only. **Do not use it in any user-facing role** (especially not medical orchestration). Replace with an aligned instruct variant before any deployment.

[PROJECT: replace with actual deploy infra for this repo if different.]

**biltiq-privacy does not deploy on the BiltIQ GPU node map above.** It's a library + sidecar — consumers (CDSCO-RegAI etc.) decide their own deployment. The GPU node map matters here only as the consumer environment for CDSCO-RegAI, which currently runs on Node 4 with FastAPI + PostgreSQL + Qdrant + Redis + MinIO.

---

## Brand rules (enforced in code, docs, and copy)

- **"IQ"** in BiltIQ wordmark is always Signal Green: `#11BB5B` (light contexts) / `#00E676` (dark contexts).
- **"Bilt"** and **"AI"** are black or white depending on surface — never optional.
- **ATC** product prefix is retained across all products. Never modified.
- Pricing is always in INR.

---

## Commercial context

- **Bootstrapped.** ~₹3 Cr FY26 revenue, ₹4 Cr expansion pipeline, ₹15 Cr FY27 target.
- **Phase-gated capital deployment:** hires and hardware only after project closure/payment.
- **Funding sequence:** non-dilutive grants (iDEX, NASSCOM/MeitY) → revenue-based financing → angel/seed post-Google Accelerator.

---

## Communications

- **Primary contact:** hello@biltiq.ai · +91 8986860088
- **Hiring:** career@biltiq.ai
- **Active domain:** biltiq.ai (atcuality.com retired; retained only for email aliases)
- **Registered address:** 72 G Road, Kadma, Jamshedpur 831005

---

## Updates to this file

- This file changes rarely. When it does, the change requires Harish's approval.
- Anything in flux (current pipeline, active bids, sprint state) lives in `MEMORY.md`, not here.
- Anything specific to one repo (e.g., a single product's architecture) lives in that repo's `/docs/architecture/`, not here.
