# Manual install: `age` 1.2.0

Operator-facing playbook for installing [FiloSottile/age](https://github.com/FiloSottile/age)
v1.2.0 on hosts where `scripts/install-age.sh` is not applicable (no shell,
no `$HOME/.local/bin` on `$PATH`, locked-down package managers, etc.) or
where the autodetect path fails. The wrapper at `biltiq_privacy.backup`
calls `age` via `subprocess.Popen`, so any installation method that lands a
working `age` binary on `$PATH` is acceptable. See ADR-0003 for the
rationale behind the system-binary approach.

`biltiq-privacy` pins `AGE_VERSION=1.2.0`. Newer 1.x releases should be
binary-compatible but are not validated by the wrapper's test matrix.

---

## Prereqs

- One of: `curl` (preferred) or `wget`.
- One of: `sha256sum` (Linux) or `shasum -a 256` (macOS).
- A writable directory on `$PATH` — `$HOME/.local/bin/` (per-user) or
  `/usr/local/bin/` (system-wide; requires `sudo`).

---

## Installation matrix

All four tarballs below ship a single `age/age` binary inside a `tar.gz`.
Extract it, place the inner binary on `$PATH`, and verify with
`age --version`.

### Linux x86_64

```sh
curl -fsSL -o age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.2.0/age-v1.2.0-linux-amd64.tar.gz
echo "2ae71cb3ea761118937a944083f057cfd42f0ef11d197ce72fc2b8780d50c4ef  age.tar.gz" | sha256sum -c -
tar -xzf age.tar.gz
mkdir -p "$HOME/.local/bin"
mv age/age "$HOME/.local/bin/age"
chmod +x "$HOME/.local/bin/age"
age --version   # expect: 1.2.0
```

### Linux arm64

```sh
curl -fsSL -o age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.2.0/age-v1.2.0-linux-arm64.tar.gz
echo "d25a81f3ac011884009d18362eeb8154ce1bca4d151834c35c718654bd6c6353  age.tar.gz" | sha256sum -c -
tar -xzf age.tar.gz
mkdir -p "$HOME/.local/bin"
mv age/age "$HOME/.local/bin/age"
chmod +x "$HOME/.local/bin/age"
age --version   # expect: 1.2.0
```

### macOS Intel (amd64)

```sh
curl -fsSL -o age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.2.0/age-v1.2.0-darwin-amd64.tar.gz
echo "d1a2277615e974be710f1a2e3c5be070bfc030d91b381ed04f41cae1a5fc2efb  age.tar.gz" | shasum -a 256 -c -
tar -xzf age.tar.gz
mkdir -p "$HOME/.local/bin"
mv age/age "$HOME/.local/bin/age"
chmod +x "$HOME/.local/bin/age"
xattr -d com.apple.quarantine "$HOME/.local/bin/age" 2>/dev/null || true
age --version   # expect: 1.2.0
```

The `xattr -d com.apple.quarantine` line removes Gatekeeper's quarantine
flag that ships with any binary downloaded via `curl`/Safari on macOS. The
`|| true` guard handles the case where the flag is already absent.

### macOS Apple Silicon (arm64)

```sh
curl -fsSL -o age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.2.0/age-v1.2.0-darwin-arm64.tar.gz
echo "f9dbc0726394f509e3d515a0bef5ffc02d8e59a818bfffc0f4acd826405af292  age.tar.gz" | shasum -a 256 -c -
tar -xzf age.tar.gz
mkdir -p "$HOME/.local/bin"
mv age/age "$HOME/.local/bin/age"
chmod +x "$HOME/.local/bin/age"
xattr -d com.apple.quarantine "$HOME/.local/bin/age" 2>/dev/null || true
age --version   # expect: 1.2.0
```

### Windows (scoop or choco)

The official `age` 1.2.0 release ships a `windows-amd64.zip`. Two
package-manager paths are simpler than manual extraction:

**Scoop:**

```powershell
scoop install age
```

**Chocolatey:**

```powershell
choco install age
```

Both place `age.exe` on `$Env:Path`. Verify with:

```powershell
age --version
```

If neither package manager is available, download the
`age-v1.2.0-windows-amd64.zip` from
<https://github.com/FiloSottile/age/releases/tag/v1.2.0>, extract, and
move `age.exe` into a directory on `$Env:Path` (`%LOCALAPPDATA%\Programs\age\`
is a common choice for per-user installs).

---

## When the autodetect script fails

| Symptom | Likely cause | Fix |
|---|---|---|
| `scripts/install-age.sh` exits 2 with "unknown OS" | `uname -s` returned something outside `Linux \| Darwin \| MINGW* \| MSYS* \| CYGWIN*` (e.g., FreeBSD, NetBSD, OpenBSD) | Use the manual install for your distro; FreeBSD tarball is at the same release URL pattern with `freebsd-amd64`. |
| `scripts/install-age.sh` exits 2 with "unknown arch" | `uname -m` returned a value outside the amd64 / arm64 mapping (e.g., `armv7l`, `riscv64`) | Use the `linux-arm` (32-bit ARM) tarball; for riscv64 there is no upstream pre-built binary — build from source per the [age README](https://github.com/FiloSottile/age#installation). |
| `SHA256 mismatch` during the tarball path | Upstream release was retagged, or a corrupt download | Re-fetch the tarball; if the mismatch persists, the SHA256 baseline embedded in `install-age.sh` is stale — open an issue and use this manual playbook in the meantime. |
| `apt-get install age` returns "Unable to locate package" | Distro too old (Debian < 12, Ubuntu < 22.04) | Use the Linux tarball path above; the binary is statically linked and works back to glibc 2.17 (CentOS 7 era). |
| `command not found: age` after install | `$HOME/.local/bin` not on `$PATH` | Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc`, then `source` it. |
| macOS: "cannot be opened because the developer cannot be verified" | Gatekeeper quarantine flag still present | Run `xattr -d com.apple.quarantine /path/to/age` (see macOS sections above). |
| Windows `scoop install age` fails with "no matching bucket" | Default scoop bucket missing the recipe | `scoop bucket add main` then re-try; or fall back to the manual `.zip` extraction. |

---

## Verification

After any install path, confirm the binary is usable end-to-end:

```sh
age --version              # expect: 1.2.0
age-keygen | tee /dev/null # generates a fresh keypair to stdout (echo only, do not commit)
```

Then run the wrapper's round-trip test against your local install:

```sh
cd <biltiq-privacy repo>
source .venv/bin/activate
pytest packages/python-core/tests/backup/test_age_stream.py -v
```

All 6 tests should pass (or skip cleanly if the age binary is somehow not
on `$PATH`).

---

## Cross-links

- [`docs/adr/0003-age-streaming-pattern.md`](../adr/0003-age-streaming-pattern.md)
  — rationale for the system-binary subprocess approach (vs. cgo bindings,
  pyca/cryptography, or a vendored Go build).
- [`scripts/install-age.sh`](../../scripts/install-age.sh) — the autodetect
  installer this runbook is the fallback for.
- [FiloSottile/age v1.2.0 release](https://github.com/FiloSottile/age/releases/tag/v1.2.0)
  — upstream artifacts + signed proofs.
