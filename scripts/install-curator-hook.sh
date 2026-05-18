#!/bin/sh
# Install (or uninstall) the biltiq-privacy memory-spine post-commit hook.
#
# Usage:
#   scripts/install-curator-hook.sh              install (idempotent)
#   scripts/install-curator-hook.sh --uninstall  remove the symlink
#   scripts/install-curator-hook.sh --force      overwrite a non-symlink occupant
#
# Contract (see AGENT_RULES.md § Memory):
#   - Refuses to clobber a non-symlink occupant of .git/hooks/post-commit
#     unless --force is passed (avoids silently overwriting another plugin's hook).
#   - --uninstall removes only symlinks that point at our hook source; refuses
#     to remove anything else.
#   - Symlink (not copy) so edits to scripts/hooks/post-commit.sh take effect
#     immediately without re-running the installer.

set -u

UNINSTALL=0
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall) UNINSTALL=1; shift ;;
        --force)     FORCE=1; shift ;;
        -h|--help)
            sed -n '2,16p' "$0"
            exit 0
            ;;
        *)
            printf 'unknown arg: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

REPO_ROOT="${BILTIQ_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$REPO_ROOT" ]; then
    printf 'error: not in a git repo and BILTIQ_REPO_ROOT not set\n' >&2
    exit 1
fi
if [ ! -d "$REPO_ROOT/.git" ]; then
    printf 'error: %s/.git does not exist\n' "$REPO_ROOT" >&2
    exit 1
fi

HOOK_SOURCE="$REPO_ROOT/scripts/hooks/post-commit.sh"
HOOK_DEST="$REPO_ROOT/.git/hooks/post-commit"

if [ "$UNINSTALL" -eq 1 ]; then
    if [ -L "$HOOK_DEST" ]; then
        TARGET=$(readlink "$HOOK_DEST")
        case "$TARGET" in
            "$HOOK_SOURCE"|"scripts/hooks/post-commit.sh"|"../../scripts/hooks/post-commit.sh")
                rm -f "$HOOK_DEST"
                printf 'uninstalled: %s\n' "$HOOK_DEST"
                exit 0
                ;;
            *)
                printf 'refusing to remove: %s -> %s (not our hook)\n' "$HOOK_DEST" "$TARGET" >&2
                exit 1
                ;;
        esac
    elif [ -e "$HOOK_DEST" ]; then
        printf 'refusing to remove: %s is not a symlink\n' "$HOOK_DEST" >&2
        exit 1
    else
        printf 'already uninstalled (nothing at %s)\n' "$HOOK_DEST"
        exit 0
    fi
fi

# Install path
if [ -L "$HOOK_DEST" ]; then
    TARGET=$(readlink "$HOOK_DEST")
    if [ "$TARGET" = "$HOOK_SOURCE" ]; then
        printf 'already installed: %s -> %s\n' "$HOOK_DEST" "$HOOK_SOURCE"
        exit 0
    fi
    if [ "$FORCE" -eq 1 ]; then
        rm -f "$HOOK_DEST"
    else
        printf 'refusing to overwrite: %s -> %s\nuse --force to override\n' "$HOOK_DEST" "$TARGET" >&2
        exit 1
    fi
elif [ -e "$HOOK_DEST" ]; then
    if [ "$FORCE" -eq 1 ]; then
        rm -f "$HOOK_DEST"
    else
        printf 'refusing to overwrite non-symlink at %s\nuse --force to override\n' "$HOOK_DEST" >&2
        exit 1
    fi
fi

if [ ! -f "$HOOK_SOURCE" ]; then
    printf 'error: hook source missing at %s\n' "$HOOK_SOURCE" >&2
    exit 1
fi

mkdir -p "$REPO_ROOT/.git/hooks"
ln -s "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_SOURCE" 2>/dev/null || true
printf 'installed: %s -> %s\n' "$HOOK_DEST" "$HOOK_SOURCE"
exit 0
