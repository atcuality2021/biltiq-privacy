# Operator runbook: issuing & rotating sidecar access tokens

Operator-facing playbook for granting clients access to the `biltiq-privacy-server`
REST sidecar (BILTIQ-013) using the `biltiq-privacy-mint` CLI (BILTIQ-013a).

The sidecar is **verify-only**: it authenticates callers by checking an HS256
JWT but never issues one. Token issuance is an *operator* action performed
out-of-band with this CLI. See [ADR-0007](../adr/0007-jwt-library-selection.md)
for the signing-library decision and the verify-only carve-out.

> **Scope of this model.** This is operator/CI-grade auth: a single shared
> symmetric secret, short-lived bearer tokens, no per-token revocation, no
> per-principal authorization. For policy/roles/scoped-key governance and
> asymmetric signing, see **BILTIQ-020** (`docs/architecture/roadmap-skyflow-parity.md`).
> Do not onboard untrusted external tenants on this model alone — read
> [§ Limitations](#limitations) first.

---

## Prereqs

- `biltiq-privacy-server` installed (provides both `biltiq-privacy-server` and
  `biltiq-privacy-mint` console-scripts).
- The shared signing secret available as `BILTIQ_JWT_SECRET` on the box you mint
  from. It **must be byte-identical** to the secret the running server verifies
  with — the same string both signs (mint) and verifies (server). HS256 is
  symmetric.
- A way to deliver the minted token to the client over a confidential channel
  (the token is a bearer credential — anyone holding it is authenticated).

---

## Generating the shared secret (one-time, per environment)

Use a high-entropy random string. Generate it once per environment (dev / staging
/ prod), store it in your secret manager, and inject it as an env var into both
the server process and the mint box.

```sh
# 32 random bytes, URL-safe base64 (~43 chars). Keep this out of shell history.
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

The server also requires `BILTIQ_HMAC_KEY` (≥ 32 bytes after utf-8 encoding) for
pseudonymisation. That key is a *server* secret only — it is never needed to mint
tokens and must never be passed to the mint CLI.

> **Never put a secret on the command line.** `biltiq-privacy-mint` reads the
> signing secret from `BILTIQ_JWT_SECRET` **only** — there is deliberately no
> `--secret` flag, because CLI arguments leak into `ps`, shell history, and
> process listings. Export it into the environment instead.

---

## Issuing a token to a client

```sh
export BILTIQ_JWT_SECRET='<same secret the server verifies with>'

# Minimal: subject (required) + default 1-hour TTL
biltiq-privacy-mint --sub acme-corp

# With a shorter TTL (seconds) and descriptive claims
biltiq-privacy-mint --sub acme-corp --ttl 900 --claim tier=standard --claim env=prod
```

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--sub` | yes | — | Subject / principal identifier (who the token is for). |
| `--ttl` | no | `3600` | Lifetime in **seconds**; must be `> 0`. Sets `exp = iat + ttl`. |
| `--claim k=v` | no | — | Extra string claim; repeatable. Split on the first `=`. |

Rules enforced by the CLI (exit `2`, message to stderr, nothing on stdout on any
violation):

- `sub`, `iat`, and `exp` are **reserved** — you cannot set them via `--claim`
  (`--sub` sets the subject; `iat`/`exp` are derived from the clock and `--ttl`).
- A `--claim` with no `=`, or an empty key (`--claim =v`), is rejected.
- A missing or empty `BILTIQ_JWT_SECRET` is rejected before any token is built.

On success the token — and **only** the token — is written to stdout as a single
line, so it is safe to capture:

```sh
TOKEN="$(biltiq-privacy-mint --sub acme-corp --ttl 900)"
```

Deliver `$TOKEN` to the client. They authenticate by sending it as a bearer
credential on every request to a data endpoint:

```sh
curl -X POST https://your-host:8088/anonymize \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Aadhaar 1234 5678 9012", "regime": "dpdp"}'
```

`GET /healthz` needs no token; `/detect`, `/anonymize`, and `/validate` all
require a valid one (uniform `401` with `WWW-Authenticate: Bearer` otherwise).

---

## Verifying a token before you hand it out

A quick local round-trip confirms the secret matches and the claims are sane,
without involving the running server:

```sh
python3 - <<'PY'
import os, jwt
tok = os.environ["TOKEN"]
print(jwt.decode(tok, os.environ["BILTIQ_JWT_SECRET"], algorithms=["HS256"]))
PY
```

The server uses exactly this algorithm allow-list (single-element `["HS256"]`),
so a token that decodes here will be accepted there — provided it has not expired
by the time the client uses it.

---

## Rotation & revocation

There is **no per-token revocation** in this model. The two levers are TTL and
secret rotation.

### Routine: short TTLs

Mint short-lived tokens (minutes to an hour) and re-issue on a schedule. A leaked
token then has a small validity window. Prefer this over long-lived tokens.

### Emergency: rotate the shared secret (revokes everyone at once)

Rotating `BILTIQ_JWT_SECRET` invalidates **all** outstanding tokens simultaneously
— there is no way to revoke a single token while leaving others valid.

1. Generate a new secret (see above) and store it in the secret manager.
2. Update the env var on the server and restart it. The server re-reads the
   secret at startup (fail-fast — it will not bind a port with a missing/empty
   secret).
3. Update `BILTIQ_JWT_SECRET` on the mint box.
4. Re-issue tokens to every active client; the old tokens now return `401`.

> During a rotation there is a brief window where in-flight clients hold tokens
> signed with the old secret and will get `401` until re-issued. Schedule
> rotations accordingly, or run a short dual-secret overlap at the load balancer
> if your topology supports it (the sidecar itself verifies against one secret).

---

## Security do / don't

- **Do** inject `BILTIQ_JWT_SECRET` via the environment from a secret manager.
- **Do** keep TTLs short; treat tokens as disposable.
- **Do** deliver tokens over a confidential channel and avoid logging them.
- **Don't** pass the secret as a CLI argument (there is no flag for it on purpose).
- **Don't** reuse one token across distinct clients — mint one per `--sub` so the
  audit trail and any future per-principal policy (BILTIQ-020) can distinguish them.
- **Don't** rely on `--claim role=...` / `tier=...` for access control today — see
  below.

---

## Limitations

These are deliberate boundaries of the current auth model, deferred to later
tickets — do not assume they exist:

- **No scope/role enforcement.** Claims such as `role` or `tier` are *carried* in
  the token but the server does not gate any endpoint on them. Every valid token
  can call all three data endpoints. Per-principal policy is **BILTIQ-020**.
- **No per-token revocation.** Mass rotation (above) is the only revocation lever.
  A revocation/denylist mechanism is folded into **BILTIQ-020**.
- **Symmetric secret.** Any party able to mint also holds the secret needed to
  forge a token, because signing and verification share one key. An asymmetric
  (RS256) sign/verify split — where the server holds only a public key and cannot
  mint — is folded into **BILTIQ-020** (deferral originates in ADR-0007).

---

## See also

- [ADR-0007 — JWT library selection](../adr/0007-jwt-library-selection.md) (verify-only carve-out, deferred RS256/revocation)
- `docs/specs/BILTIQ-013/` — sidecar spec/design
- `docs/specs/BILTIQ-013a/` — mint-CLI spec/design
- `docs/architecture/roadmap-skyflow-parity.md` § BILTIQ-020 — governance, roles, scoped keys
