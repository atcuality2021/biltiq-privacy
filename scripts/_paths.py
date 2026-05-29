# SYNC-HEADER:
#   source: ~/.claude/plugins/cache/biltiq-internal/biltiq-engineering/1.10.1/scripts/_paths.py
#   sha256: 7b98066c3a5926cccbec961455dcc3688602d199496557359d978b21fb6ba62e
#   synced: 2026-05-29
#   adr:    docs/adr/0004-memory-spine-vendoring.md
# END-SYNC-HEADER
"""Plugin-internal path utilities — single source of truth for repo-root + repo-hash.

Plan reference: docs/specs/M19-plugin-review-sweep/M19b-subagent-wiring-and-dedup/plan.md § Step 1.

Two surfaces in one file (dual module + CLI per design.md Alt 1) so bash hooks can
invoke `python3 ${PLUGIN_ROOT}/scripts/_paths.py --hash <root>` without any
PYTHONPATH gymnastics, while spine modules import the functions directly.

Public surface:
    _resolve_repo_root(repo_root: str | Path | None = None) -> Path
        Precedence: explicit arg > CLAUDE_PROJECT_DIR env > cwd. Dual-type input
        (str or Path) decided 2026-05-04 to preserve backward compat with 4
        spine call sites that currently pass str.

    _repo_hash(repo_root: Path) -> str
        sha1[:12] of the path bytes — used to derive
        ~/.biltiq-engineering/<hash>/ directory names.

CLI:
    python3 _paths.py --root [PATH]   Print resolved repo root.
    python3 _paths.py --hash <PATH>   Print sha1[:12] of PATH.

No external dependencies. Python 3.9 floor (matches plugin-wide stance per
docs/architecture/approved-versions.md).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path


def _resolve_repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root:
        return Path(repo_root).resolve()
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def _repo_hash(repo_root: Path) -> str:
    return hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:12]


def _safe_write(target: Path, content: str) -> None:
    """Atomically write content to target. Stage to <target>.tmp, then rename.

    Contract: on success, target contains content as a single atomic operation
    (POSIX rename guarantee on the same filesystem). On failure, target is
    unchanged on disk and the .tmp staging file is cleaned up. The original
    exception re-raises so the caller can decide how to react.

    Narrow exception scope per BILTIQ-020 AC8: only file-system errors caught
    (OSError covers BlockingIOError, FileNotFoundError, PermissionError,
    IsADirectoryError, etc. — all under the OSError hierarchy). MemoryError,
    KeyboardInterrupt, etc. propagate without cleanup attempt (system-level
    signals).
    """
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        # Path.replace uses os.replace under the hood — cross-platform atomic
        # replacement (MoveFileExW(MOVEFILE_REPLACE_EXISTING) on Windows).
        # Path.rename would fail on Windows if target exists.
        tmp.replace(target)
    except OSError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass  # cleanup is best-effort; original error is what matters
        raise


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="_paths",
        description="Plugin-internal path utilities (CLI surface for hook scripts).",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument(
        "--root",
        nargs="?",
        const="",
        metavar="PATH",
        help="Print the resolved repo root. Bare --root uses CLAUDE_PROJECT_DIR/cwd.",
    )
    grp.add_argument(
        "--hash",
        metavar="PATH",
        help="Print sha1[:12] of PATH (used for state-dir derivation in hook scripts).",
    )
    args = parser.parse_args(argv)

    if args.root is not None:
        print(_resolve_repo_root(args.root or None))
        return 0
    if args.hash is not None:
        print(_repo_hash(Path(args.hash)))
        return 0
    return 1  # unreachable: required mutually-exclusive group


if __name__ == "__main__":
    sys.exit(_main())
