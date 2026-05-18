#!/bin/sh
# Post-commit hook for biltiq-privacy memory spine.
#
# Contract (see AGENT_RULES.md § Memory):
#   - Never exits non-zero. A curator crash never aborts the commit.
#   - Runs the curator in the background; foreground commit returns immediately.
#   - Appends only curator stdout/stderr to .biltiq/curator-hook.log (structured
#     JSON event counts + tracebacks if any; no event-payload contents).
#
# Installed via scripts/install-curator-hook.sh. Opt-in; not installed by default.

REPO_ROOT="${BILTIQ_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$REPO_ROOT" ] && exit 0

mkdir -p "$REPO_ROOT/.biltiq" 2>/dev/null

nohup python3 "$REPO_ROOT/scripts/_memory_curator.py" \
    >> "$REPO_ROOT/.biltiq/curator-hook.log" 2>&1 &

exit 0
