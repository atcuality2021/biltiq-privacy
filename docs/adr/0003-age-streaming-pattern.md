# ADR 0003: age system-binary wrapper via `subprocess.Popen` streaming

**Status:** proposed
**Date:** 2026-05-18
**Deciders:** @harish (dev), @claude (architect via biltiq-code-architect subagent)
**Related task:** BILTIQ-004
**Related ADRs:** [`CDSCO-RegAI:docs/adr/0002-age-encryption-for-backups.md`](../../../cdcso/CDSCO-RegAI/docs/adr/0002-age-encryption-for-backups.md) (the upstream rationale source, re-derived here for the library audience)

---

## Context

`docs/architecture/stack.md` § Encryption (line 52) advertises the age system binary "wrapped via `subprocess.Popen` for streaming `pg_dump | age` pipelines" with installation via `scripts/install-age.sh`. Neither the Python wrapper module nor the install script existed prior to BILTIQ-004; the line is the architectural commitment, not the code that satisfies it.

BILTIQ-004 ships the wrapper module (`biltiq_privacy.backup.age_stream`), the install script, the manual-install runbook, and this ADR locking the implementation pattern. The pattern is non-trivial in three ways that justify an ADR:

1. **Encryption backend choice.** The library could (a) shell out to the system age binary via subprocess, (b) embed a Python age implementation, (c) hand-roll X25519 + ChaCha20-Poly1305 over the `cryptography` library, or (d) FFI into the Go `age` library. The architectural decision affects supply-chain surface, on-prem deploy story, cross-tool format compatibility, and CI matrix complexity for the life of v0.5.0+.

2. **Streaming versus tmp-file shape.** Two integration patterns produce the same external behaviour: streaming plaintext through a pipe to a subprocess (no plaintext on disk) or writing plaintext to a temporary file, encrypting the tmp, deleting the tmp. The first is harder to write (lifecycle management of the subprocess, pipe-buffer behaviour, exception cleanup); the second is forbidden by spec AC2/AC3 of BILTIQ-004 ("no plaintext on disk") and by the upstream CDSCO-RegAI ADR-0002 § Decision rule 3. Locking the streaming choice here prevents future "simplification" PRs from regressing the guarantee.

3. **Exception hierarchy.** Library callers want to handle "binary not installed" and "binary exited non-zero" separately, but without importing private exception classes. Subclassing stdlib base classes (`FileNotFoundError` and `subprocess.CalledProcessError`) is one valid choice; a library-internal `BackupError` / `RestoreError` hierarchy (as CDSCO-RegAI uses, since CDSCO-RegAI was an application not a library) is another. The two have different callsite ergonomics.

Compliance mode is `on_prem_preferred` (AGENT_RULES.md). The wrapper introduces no external AI / cloud calls; this ADR is an architectural-decision ADR, not a compliance-override ADR. Recording the choice in an ADR is good hygiene for a v0.5.0+ load-bearing decision regardless.

## Decision

Use the **system `age` binary (FiloSottile/age, v1.2.x)** invoked via **`subprocess.Popen` with `stdin=PIPE` (writer) or `stdout=PIPE` (reader)**, wrapped by two `@contextmanager`-decorated generator functions in `packages/python-core/biltiq_privacy/backup/age_stream.py`:

- **Writer:** `open_age_writer(out_path: Path, *, recipient: str) -> Iterator[IO[bytes]]`. Invokes `subprocess.Popen(["age", "-r", recipient, "-o", str(out_path)], stdin=PIPE, stderr=PIPE)`. Yields `proc.stdin` to the caller; the caller writes plaintext bytes. At `__exit__`, `stdin` is closed, the process is waited on, `stderr` is captured. Non-zero exit raises `AgeProcessError` (subclass of `subprocess.CalledProcessError`).
- **Reader:** `open_age_reader(in_path: Path, *, identity_path: Path) -> Iterator[IO[bytes]]`. Invokes `subprocess.Popen(["age", "-d", "-i", str(identity_path), str(in_path)], stdout=PIPE, stderr=PIPE)`. Yields `proc.stdout` to the caller; the caller reads decrypted plaintext bytes. Same `__exit__` cleanup contract as the writer.

Both context managers check `shutil.which("age")` at `__enter__`. Absence raises `AgeNotInstalledError` (subclass of `FileNotFoundError`).

Both context managers wrap their `yield` in `try / except BaseException / finally`. The `BaseException` branch closes the pipe handles, waits the subprocess, unlinks any partial ciphertext file (writer path), and re-raises. The `finally` always drains and closes `stderr`. Orphaned `age` subprocesses are not produced by any normal or exceptional exit path.

The wrapper is **stateless / IO-only**. No module-global cache, no env reads, no key persistence, no recipient-resolution. Callers (the BILTIQ-005+ backup orchestrator) own those concerns.

The CLI surface for operators is **`scripts/install-age.sh`** &mdash; POSIX-`sh`, autodetect order `apt-get → dnf → pacman → snap → GitHub-release tarball` on Linux, `Homebrew → GitHub-release tarball` on macOS, `directive to scoop / choco + exit 2` on Windows MSYS2 / Cygwin / MinGW shells. The script is the only place this ticket touches the supply-chain trust boundary directly (via SHA256 verification of the GitHub-release tarball against a committed-in-script baseline).

## Alternatives considered

1. **Pure-Python age library (a hypothetical `pyage` PyPI package).** Rejected. No actively-maintained Python port at production quality as of 2026-05; the partial ports lag the age v1 spec on plugins / passphrase flows. Adds a new runtime dependency to the library &mdash; auto-blocked by stack.md § "Library framework: NONE" without an ADR override. The library + sidecar's deploy story is "native pip + systemd, ~120 MB RAM" (AGENT_RULES.md § Project context); pulling X25519 + ChaCha20-Poly1305 into the Python process raises the supply-chain surface for a problem the canonical implementation already solves with a single static binary.

2. **`cryptography` library + hand-rolled X25519 / ChaCha20-Poly1305 pipeline implementing age v1 wire format.** Rejected. Re-implements a spec'd, audited binary protocol &mdash; one-engineer-year scope. Format compatibility with downstream tooling (CDSCO-RegAI's restore script, sops-age, k8s sealed-secrets, drone-ci age plugins) would be a maintenance treadmill against the upstream age repo. Adds `cryptography` as a hard runtime dependency. Brief §2 rule 1 ("depend, pin, never fork") applies by analogy: we depend on age the binary; we do not fork its protocol into Python.

3. **FFI to the `age` Go library via `ctypes` against a CGo-built shared object.** Rejected. Adds a build-time dependency on the Go toolchain for every CI matrix cell. Cross-compile matrix (linux x86_64, linux arm64, macOS Intel + Apple Silicon, Windows) is 5+ binaries to ship per release; the system-binary path delegates this to the upstream age release page. FFI surface adds segfault risk for a class of problem (subprocess pipe streaming) where Python's stdlib is the right shape.

4. **`NamedTemporaryFile` + non-streaming subprocess call: write plaintext to a tmp file, encrypt the tmp, delete the tmp.** Rejected. Plaintext materialises on disk for the duration of the age call &mdash; BILTIQ-004 spec AC2/AC3 explicitly forbid this shape. Even with `tempfile` auto-unlink, an interrupted run leaves a window where the plaintext is on disk in a predictable temp location. CDSCO-RegAI's ADR-0002 § Decision rule 3 ("encryptable from a `subprocess.Popen` pipeline so plaintext never lands on disk") is the prior-art source for the same rule.

5. **Library-internal `BackupError` / `RestoreError` exception hierarchy** (as CDSCO-RegAI's `scripts/_backup_lib/errors.py` ships). Rejected for the library. CDSCO-RegAI was an application; biltiq-privacy is a library. Library callers want to `except FileNotFoundError` (for missing binary) and `except subprocess.CalledProcessError` (for non-zero exit) without importing our private exception class. Subclassing the stdlib bases gives callers both surfaces without forcing the import.

6. **Single `AgeError` class for both failure modes.** Rejected. Conflates two operationally-different conditions: "age isn't installed" (the operator needs to run the install script) versus "age exited non-zero" (a recipient / identity / ciphertext-corruption problem). BILTIQ-004 spec AC1 and AC4 keep them separate; the chosen design preserves that.

## Consequences

**Positive:**

- One static binary (~5 MB), zero runtime dependencies added to the Python library. Installable on an air-gapped appliance via offline `.deb` or static-binary copy &mdash; the manual-install runbook covers this.
- `age` is widely adopted in the ops-tooling ecosystem (drone-ci, sops-age, k8s sealed-secrets via age, mozilla/sops). Operator knowledge is portable; format inspection tools exist outside this codebase.
- Streaming through a pipe means the "no plaintext PII on disk" invariant is provable by code review (the implementation never instantiates a tmp file), not aspirational. The directory-walk regex grep for plaintext PII over a backup tree becomes a reliable post-condition.
- Asymmetric exception hierarchy: `except FileNotFoundError` matches the install-time failure mode; `except subprocess.CalledProcessError` matches the runtime failure mode. Both are stdlib idioms; library consumers add no imports for broad handling.
- Compliance-clean. No external AI / cloud calls. No HTTP client added to the library. The on-prem-preferred mode's gates do not fire.
- Cross-tool format compatibility: any `.age`-encrypted file the wrapper produces can be decrypted by any version-matching `age` binary anywhere, including outside this codebase. Restores survive a complete loss of the appliance plus the wrapper code, as long as the operator has the identity key and an `age` binary &mdash; the spec's compliance posture for a regulated audit export.

**Negative / risks:**

- Subprocess lifecycle management is non-trivial. The `try / except BaseException / finally` pattern in the wrapper must close pipe handles, wait the subprocess, and unlink partial ciphertext on every exit path. A bug here yields orphaned `age` processes or partial-encrypted files. Mitigated by a dedicated "writer body raises mid-stream" test in `test_age_stream.py` beyond what BILTIQ-004 AC4 strictly demands. Risk #2 in BILTIQ-004 design.html.
- "No plaintext on disk" is a code-review invariant, not a runtime test. A future refactor that introduces a `NamedTemporaryFile` between the caller and the subprocess passes all runtime tests but breaks the invariant. Mitigated by the code-reviewer skill's static check and by an explicit "DO NOT introduce intermediate plaintext files" comment in the wrapper's module docstring. Risk #3 in BILTIQ-004 design.html.
- Install script paths are only fully validated on Linux during local development. GitHub-hosted CI exercises Linux and macOS; the Windows-shell branch is correct-by-inspection. Risk #1 in BILTIQ-004 design.html; gaps land in the PR description's "known unvalidated paths" section.
- `age` format stability is a bet (v1.0 in 2022; format is intentionally minimal and the spec is published). If the upstream maintainers ever introduce a v2 with breaking format changes, the wrapper would need a version-pin and a backward-read path. The pin in `scripts/install-age.sh` (`AGE_VERSION="1.2.0"`) is the load-bearing lever.
- SHA256 baseline in the install script goes stale when age releases a new version. Mitigation: SHA256-mismatch exits `1` with a clear message pointing the operator at the manual-install runbook. Operators are never silently exposed to a tampered tarball. Risk #4 in BILTIQ-004 design.html.

**Tech debt accepted:**

- No static-analysis lint rule enforces the "no plaintext on disk" invariant. Code reviewer attention is the gate. Long-term, a ruff plugin or a custom check in `biltiq-gates.yml` could codify this; out of scope for BILTIQ-004.
- No CI matrix cell for the macOS Homebrew install path or the Windows MSYS2 install path. Manual verification at Step 5 (Test) is the gate; out of scope to extend CI here.
- The wrapper does not abstract age-keygen / recipient-file layout / manifest signing &mdash; those are the v0.5.0+ orchestrator's job (BILTIQ-005+, explicitly carved out by BILTIQ-004 spec § Out of Scope). The CDSCO-RegAI `config/age-recipients/<APPLIANCE_ID>/` convention may or may not be ported when the orchestrator ships; this ADR takes no position.

## How this gets enforced

- `scripts/check-boundaries.sh` (BILTIQ-001) blocks any FastAPI / Starlette / uvicorn import in `packages/python-core/`; the wrapper has no web-framework imports to flag.
- `code-reviewer` skill checks the wrapper module against the 10 anti-patterns plus the "no plaintext on disk" static check (Risk #3).
- `anti-pattern-scanner` skill runs against `packages/python-core/biltiq_privacy/backup/age_stream.py` during Step 4 (Review).
- `pytest packages/python-core/tests/backup/` runs the round-trip + error-path tests, gated by `pytest.mark.skipif(not shutil.which("age"))` on the age-dependent tests so the CI matrix stays green on cells where age is not pre-installed (BILTIQ-004 AC6).
- `shellcheck scripts/install-age.sh` runs in CI to catch shell-quoting / syntax errors on all branches of the install script.
- `docs/architecture/stack.md` § Internal modules registers `biltiq_privacy.backup.age_stream` in the same PR that creates it (the anti-pattern #1 defence surface).

## What this ADR does NOT cover

- **Key custody mechanism** (HSM, YubiKey, sealed env, paper backup). Deferred to the BILTIQ-005+ orchestrator and follow-up tasks. The wrapper takes a caller-supplied recipient string and identity path; how those are stored, rotated, or recovered is not its concern.
- **Per-appliance keypair layout** (the CDSCO-RegAI `config/age-recipients/<APPLIANCE_ID>/` convention). Deferred to BILTIQ-005+. The wrapper has no concept of "appliance".
- **Key rotation policy.** Deferred to BILTIQ-005+. The age format supports re-encryption to a new recipient without re-encrypting the underlying data, so the seam exists.
- **Format compatibility with CDSCO-RegAI backup bundles.** The wrapper handles bare `.age` files in both directions but does not promise to read CDSCO-RegAI's manifest-bundled archives. That is an orchestrator concern.
- **Native PowerShell `.ps1` installer for Windows.** Carved out by BILTIQ-004 spec § Out of Scope §5. A follow-up if Windows-native operator demand materialises.
- **Async / `asyncio` variant of the context managers.** Carved out by BILTIQ-004 spec § Out of Scope §6. The streaming pattern is naturally sync; an async adapter is a follow-up if a consumer needs it.

## References

- [age v1 spec](https://age-encryption.org/v1) &mdash; format definition.
- [FiloSottile/age GitHub releases](https://github.com/FiloSottile/age/releases) &mdash; binary release page that `scripts/install-age.sh` fetches against in the fallback path.
- [`CDSCO-RegAI/docs/adr/0002-age-encryption-for-backups.md`](../../../cdcso/CDSCO-RegAI/docs/adr/0002-age-encryption-for-backups.md) &mdash; upstream ADR; this ADR is re-derived from it for the library audience. Not copied verbatim &mdash; the library-vs-application distinction changes the exception-hierarchy decision (CDSCO-RegAI uses `BackupError`/`RestoreError`; biltiq-privacy uses stdlib subclasses) and the scope decision (CDSCO-RegAI's ADR-0002 covers per-appliance keypair layout + manifest signing; this ADR explicitly defers those to the BILTIQ-005+ orchestrator).
- [`CDSCO-RegAI/scripts/_backup_lib/age_stream.py`](../../../cdcso/CDSCO-RegAI/scripts/_backup_lib/age_stream.py) &mdash; prior-art implementation; the BILTIQ-004 wrapper ports the `subprocess.Popen` + `try / except BaseException / finally` lifecycle pattern, modulo the new exception class names.
- [`docs/specs/BILTIQ-004/spec.html`](../specs/BILTIQ-004/spec.html) &mdash; 9 ACs that this ADR's decision satisfies.
- [`docs/specs/BILTIQ-004/design.html`](../specs/BILTIQ-004/design.html) &mdash; full design rationale, alternatives table, risk register.
- [`docs/architecture/stack.md`](../architecture/stack.md) § Encryption (line 52) &mdash; pre-locked architectural commitment that BILTIQ-004 satisfies.
- AGENT_RULES.md § Compliance mode: `on_prem_preferred`. No external AI / cloud calls introduced; this ADR is an architectural-decision record, not a compliance-override record.
- BILTIQ-001 scaffold (`packages/python-core/biltiq_privacy/backup/__init__.py`) &mdash; pre-reserved sub-package with the docstring contract that BILTIQ-004 fulfils.

## Change History

| Date | Section | What Changed | Trigger |
|------|---------|--------------|---------|
| 2026-05-18 | all | Initial draft &mdash; locks the `subprocess.Popen` streaming choice over four rejected alternatives for the encryption backend and two rejected alternatives for the exception hierarchy. Status `proposed`; flipped to `accepted` at BILTIQ-004 Step 6 Ship. | BILTIQ-004 Step 2 Plan, design.html § Files to Touch |
