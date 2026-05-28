#!/bin/sh
# Install (or uninstall) the FiloSottile/age binary for biltiq-privacy.
#
# Usage:
#   scripts/install-age.sh              autodetect OS, install age (idempotent)
#   scripts/install-age.sh --force      overwrite an existing age >= 1.2.0
#   scripts/install-age.sh --uninstall  remove the script-installed binary
#   scripts/install-age.sh --dry-run    print what would be installed; do nothing
#   scripts/install-age.sh -h|--help    print this header
#
# Environment:
#   BILTIQ_AGE_DRY_RUN=1                same as --dry-run
#
# Contract:
#   - Pinned to age 1.2.0. Tarball path verifies SHA256 against a
#     committed-in-script baseline computed from the upstream release.
#   - Writes a sentinel at $HOME/.local/share/biltiq-privacy/
#     age-installed-by-script for tarball installs only, so --uninstall
#     removes only what this script placed.
#   - Refuses to overwrite an existing age >= 1.2.0 unless --force.
#   - For package-manager installs (apt/dnf/pacman/snap/brew), use the
#     package manager's own uninstall path. The sentinel is not written
#     in those cases.
#   - macOS Homebrew and Windows MSYS2 branches are correct-by-inspection
#     at write-time; cross-OS validation belongs at Attack Loop Step 5.
#     See docs/runbooks/install-age.md for the manual install playbook.

set -u

AGE_VERSION="1.2.0"
RELEASE_URL_BASE="https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}"
SENTINEL_DIR="${HOME}/.local/share/biltiq-privacy"
SENTINEL_FILE="${SENTINEL_DIR}/age-installed-by-script"
INSTALL_BIN_DIR="${HOME}/.local/bin"
INSTALL_BIN="${INSTALL_BIN_DIR}/age"

# SHA256 baselines, computed at write-time from upstream v1.2.0 release.
# Regenerate via: sha256sum age-v1.2.0-${os}-${arch}.tar.gz after downloading from $RELEASE_URL_BASE.
LINUX_AMD64_SHA256="2ae71cb3ea761118937a944083f057cfd42f0ef11d197ce72fc2b8780d50c4ef"
LINUX_ARM64_SHA256="d25a81f3ac011884009d18362eeb8154ce1bca4d151834c35c718654bd6c6353"
DARWIN_AMD64_SHA256="d1a2277615e974be710f1a2e3c5be070bfc030d91b381ed04f41cae1a5fc2efb"
DARWIN_ARM64_SHA256="f9dbc0726394f509e3d515a0bef5ffc02d8e59a818bfffc0f4acd826405af292"

UNINSTALL=0
FORCE=0
DRY_RUN="${BILTIQ_AGE_DRY_RUN:-0}"

_help() {
    sed -n '2,27p' "$0"
}

_run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] would run: %s\n' "$*"
    else
        "$@"
    fi
}

_detect_os() {
    case "$(uname -s)" in
        Linux)   printf 'linux\n' ;;
        Darwin)  printf 'macos\n' ;;
        MINGW*|MSYS*|CYGWIN*) printf 'windows-shell\n' ;;
        *)       printf 'unknown\n' ;;
    esac
}

_detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64) printf 'amd64\n' ;;
        aarch64|arm64) printf 'arm64\n' ;;
        *) printf 'unknown\n' ;;
    esac
}

_verify_age_version() {
    if ! command -v age >/dev/null 2>&1; then
        return 1
    fi
    existing=$(age --version 2>&1 | head -n 1)
    case "$existing" in
        *1.2.*|*1.3.*|*1.4.*|*1.5.*|*1.6.*|*1.7.*|*1.8.*|*1.9.*|*2.*)
            printf 'age already installed at %s: %s\n' "$(command -v age)" "$existing"
            if [ "$FORCE" -eq 0 ]; then
                printf '(pass --force to overwrite; or --uninstall first)\n'
                return 0
            fi
            printf '%s\n' '--force given; will overwrite'
            return 1
            ;;
        *)
            printf 'age present but version < 1.2.0 (%s); will reinstall\n' "$existing"
            return 1
            ;;
    esac
}

_write_sentinel() {
    _run mkdir -p "$SENTINEL_DIR"
    if [ "$DRY_RUN" -eq 0 ]; then
        printf '%s\n' "$INSTALL_BIN" > "$SENTINEL_FILE"
    else
        printf '[dry-run] would write sentinel: %s -> %s\n' "$SENTINEL_FILE" "$INSTALL_BIN"
    fi
}

_install_tarball() {
    os="$1"
    arch="$2"
    case "${os}-${arch}" in
        linux-amd64)  expected_sha="$LINUX_AMD64_SHA256"; remote_os="linux"; remote_arch="amd64" ;;
        linux-arm64)  expected_sha="$LINUX_ARM64_SHA256"; remote_os="linux"; remote_arch="arm64" ;;
        macos-amd64)  expected_sha="$DARWIN_AMD64_SHA256"; remote_os="darwin"; remote_arch="amd64" ;;
        macos-arm64)  expected_sha="$DARWIN_ARM64_SHA256"; remote_os="darwin"; remote_arch="arm64" ;;
        *)
            printf 'tarball install not supported for %s-%s; see docs/runbooks/install-age.md\n' "$os" "$arch" >&2
            return 1
            ;;
    esac
    tarball="age-v${AGE_VERSION}-${remote_os}-${remote_arch}.tar.gz"
    url="${RELEASE_URL_BASE}/${tarball}"
    tmp=$(mktemp -d -t biltiq-install-age.XXXXXX)
    printf 'fetching: %s\n' "$url"
    _run curl -fsSL -o "${tmp}/${tarball}" "$url" || {
        printf 'curl failed: %s\n' "$url" >&2
        rm -rf "$tmp"
        return 1
    }
    if [ "$DRY_RUN" -eq 0 ]; then
        actual_sha=$(sha256sum "${tmp}/${tarball}" 2>/dev/null | awk '{print $1}')
        if [ -z "$actual_sha" ]; then
            actual_sha=$(shasum -a 256 "${tmp}/${tarball}" | awk '{print $1}')
        fi
        if [ "$actual_sha" != "$expected_sha" ]; then
            printf 'SHA256 mismatch for %s\n  expected: %s\n  actual:   %s\n' "$tarball" "$expected_sha" "$actual_sha" >&2
            rm -rf "$tmp"
            return 1
        fi
        printf 'SHA256 ok: %s\n' "$actual_sha"
    else
        printf '[dry-run] would verify SHA256: %s\n' "$expected_sha"
    fi
    _run tar -xzf "${tmp}/${tarball}" -C "$tmp"
    _run mkdir -p "$INSTALL_BIN_DIR"
    _run mv "${tmp}/age/age" "$INSTALL_BIN"
    _run chmod 0755 "$INSTALL_BIN"
    _write_sentinel
    rm -rf "$tmp"
    printf 'installed: %s\n' "$INSTALL_BIN"
    # shellcheck disable=SC2016  # $PATH is literal text in the user-facing reminder
    printf '(ensure %s is on $PATH)\n' "$INSTALL_BIN_DIR"
}

_install_linux() {
    arch="$1"
    if command -v apt-get >/dev/null 2>&1; then
        printf 'detected apt-get; installing age via apt\n'
        _run sudo apt-get update -qq
        _run sudo apt-get install -y age && return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
        printf 'detected dnf; installing age via dnf\n'
        _run sudo dnf install -y age && return 0
    fi
    if command -v pacman >/dev/null 2>&1; then
        printf 'detected pacman; installing age via pacman\n'
        _run sudo pacman -S --noconfirm age && return 0
    fi
    if command -v snap >/dev/null 2>&1; then
        printf 'detected snap; installing age via snap\n'
        _run sudo snap install age && return 0
    fi
    printf 'no system package manager found; falling back to tarball\n'
    _install_tarball linux "$arch"
}

_install_macos() {
    arch="$1"
    # TODO(BILTIQ-004-AttackLoop-Step5): validate this branch on macOS hardware.
    # Homebrew lookup + tarball fallback is correct-by-inspection at write-time
    # only. Verify on macOS Intel + Apple Silicon before merge.
    if command -v brew >/dev/null 2>&1; then
        printf 'detected Homebrew; installing age via brew\n'
        _run brew install age && return 0
    fi
    printf 'Homebrew not found; falling back to tarball\n'
    _install_tarball macos "$arch"
}

_install_windows_shell() {
    # TODO(BILTIQ-004-AttackLoop-Step5): validate this branch on Windows MSYS2.
    # The directive-emit approach (scoop / choco) is correct-by-inspection only.
    printf 'Windows shell (MSYS2/Cygwin/MinGW) detected.\n' >&2
    printf 'This script does not autoinstall on Windows. Use one of:\n' >&2
    printf '  scoop install age\n' >&2
    printf '  choco install age\n' >&2
    printf 'Or follow docs/runbooks/install-age.md for the manual playbook.\n' >&2
    exit 2
}

_uninstall() {
    if [ ! -f "$SENTINEL_FILE" ]; then
        printf 'no script-installed age binary; refusing to uninstall\n' >&2
        printf '(if you installed age via apt/dnf/pacman/brew, use that package manager to remove it)\n' >&2
        exit 2
    fi
    installed_path=$(cat "$SENTINEL_FILE")
    if [ -f "$installed_path" ]; then
        _run rm -f "$installed_path"
        printf 'removed: %s\n' "$installed_path"
    else
        printf 'sentinel pointed at %s but file missing; cleaning up sentinel anyway\n' "$installed_path" >&2
    fi
    _run rm -f "$SENTINEL_FILE"
    rmdir "$SENTINEL_DIR" 2>/dev/null || true
    printf 'uninstall complete\n'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall) UNINSTALL=1; shift ;;
        --force)     FORCE=1; shift ;;
        --dry-run)   DRY_RUN=1; shift ;;
        -h|--help)   _help; exit 0 ;;
        *)
            printf 'unknown arg: %s\n' "$1" >&2
            printf 'try: %s --help\n' "$0" >&2
            exit 2
            ;;
    esac
done

if [ "$UNINSTALL" -eq 1 ]; then
    _uninstall
    exit 0
fi

os=$(_detect_os)
arch=$(_detect_arch)
printf 'detected OS: %s, arch: %s\n' "$os" "$arch"

if [ "$os" = "unknown" ]; then
    printf 'unknown OS (uname -s: %s); see docs/runbooks/install-age.md\n' "$(uname -s)" >&2
    exit 1
fi
if [ "$arch" = "unknown" ] && [ "$os" != "windows-shell" ]; then
    printf 'unknown arch (uname -m: %s); see docs/runbooks/install-age.md\n' "$(uname -m)" >&2
    exit 1
fi

if _verify_age_version; then
    exit 0
fi

case "$os" in
    linux)          _install_linux "$arch" ;;
    macos)          _install_macos "$arch" ;;
    windows-shell)  _install_windows_shell ;;
esac
