# ADR 0007: JWT library selection — PyJWT for verify-only Bearer auth

**Status:** proposed
**Date:** 2026-06-21
**Deciders:** @atcuality2021
**Related task:** BILTIQ-013

## Context

BILTIQ-013 adds Bearer-JWT authentication to the FastAPI sidecar
(`packages/python-server`). The server must **verify** HS256-signed tokens
(signature + expiry) on the three data endpoints (`/detect`, `/anonymize`,
`/validate`); it does **not** issue them — token minting is the consumer's
concern (spec § Out of Scope). This is the first crypto-adjacent dependency in
the server package, and the repo rule is that any new dependency is recorded in
an ADR and in `approved-versions.md`. The spec named two candidates and
expressed a PyJWT preference; the dev confirmed PyJWT on 2026-06-21. This ADR
records the decision.

## Decision

Use **PyJWT >= 2.8, < 3** with HS256, verify-only. Verification pins a
single-element algorithm allow-list and enables expiry checking:

```python
jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": True})
```

`auth.py` is the only module that imports `jwt`. Production code contains no
`jwt.encode` call — only the test fixture mints tokens. Missing / malformed /
expired / wrong-secret tokens all map to `401` via the `require_jwt`
dependency. The JWT secret is read once from `BILTIQ_JWT_SECRET` at startup
(`load_settings()` fast-fail) and is never logged.

## Alternatives considered

1. **`python-jose[cryptography]`** — Rejected: slower release cadence and a
   history of key-confusion / algorithm-confusion CVEs; pulls a heavier
   `cryptography` backend than HS256 verify-only needs.
2. **Roll our own HMAC verify** — Rejected: re-implementing JWT
   parsing/validation is exactly the crypto-adjacent code that should reuse a
   maintained, audited library; high risk for zero benefit.
3. **`authlib`** — Rejected: broad OAuth/OIDC surface far exceeds a verify-only
   HS256 need; larger dependency and attack surface than the task warrants.

## Consequences

**Positive:**
- Lighter dependency, active maintenance, smaller attack surface.
- Explicit single-element algorithm allow-list closes the alg-confusion class
  (the canonical JWT verification footgun).
- Verify-only keeps the server out of the token-issuance blast radius.

**Negative / risks:**
- Consumers must mint tokens themselves; documented in the README server
  quickstart (aligns with the spec's out-of-scope on token issuance).
- New runtime dependency added to `packages/python-server/pyproject.toml` and
  recorded in `approved-versions.md`.

**Tech debt accepted:**
- No key rotation / JWKS support at v0.1.0 — a single shared HS256 secret. RS256
  / asymmetric keys and rotation are deferred (spec § Out of Scope, v0.2.0).

## References
- `docs/specs/BILTIQ-013/spec.html` (AC5), `design.html` (§ Security & Compliance, ADR-0007 draft)
- PyJWT algorithm-confusion guidance: pin `algorithms=[...]` explicitly on `decode`.
