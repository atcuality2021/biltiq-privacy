#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# check-boundaries.sh -- enforce the library/server boundary (AC9 of BILTIQ-001).
#
# packages/python-core/ is the publishable library distribution `biltiq-privacy`.
# It must not depend on a web framework -- consumers running on_prem_required
# (CDSCO-RegAI healthcare, DPDP-sensitive deployments) need to pip-install the
# library without dragging fastapi/starlette/uvicorn into a regulated airgap.
# Web-framework code belongs in packages/python-server/ (`biltiq-privacy-server`)
# which is a separate distribution.
#
# This script greps every .py file under packages/python-core/ for forbidden
# top-level import statements and exits non-zero if any are found. It is
# invoked by .github/workflows/ci.yml as a dedicated boundary-check job and is
# also runnable locally before a push:
#
#     bash scripts/check-boundaries.sh
#
# Exits 0 on a clean tree, 1 on any boundary violation (offending lines printed
# to stderr in `file:line: <line>` form for IDE-friendly navigation).
#
# Boundary widening (allowing a web-framework import in packages/python-core/)
# requires an ADR per AGENT_RULES.md and a corresponding edit to the regex below
# -- removing the offending module name from the FORBIDDEN list.

set -euo pipefail

CORE_DIR="packages/python-core"
FORBIDDEN_REGEX='^[[:space:]]*(from|import)[[:space:]]+(fastapi|starlette|uvicorn)([[:space:]\.]|$)'

if [[ ! -d "${CORE_DIR}" ]]; then
    echo "check-boundaries.sh: error: ${CORE_DIR}/ not found (run from repo root)" >&2
    exit 2
fi

# grep -r with --include='*.py' walks every .py file under CORE_DIR.
# -E enables extended regex; -H forces filename prefix; -n adds line numbers.
# We capture grep's output (not its exit code via set -e) so we can print a
# helpful message before exiting non-zero.
matches="$(grep -rEHn --include='*.py' "${FORBIDDEN_REGEX}" "${CORE_DIR}" || true)"

if [[ -n "${matches}" ]]; then
    {
        echo "check-boundaries.sh: FAIL"
        echo
        echo "The publishable library distribution biltiq-privacy"
        echo "(${CORE_DIR}/) must not import fastapi, starlette, or uvicorn."
        echo "Web-framework code belongs in packages/python-server/."
        echo
        echo "Offending lines:"
        # Re-format `file:line:content` -> `  file:line: content` for readability.
        echo "${matches}" | sed 's/^/  /'
        echo
        echo "If this import is intentional (rare), record an ADR under"
        echo "docs/adr/ and remove the module name from FORBIDDEN_REGEX in"
        echo "${0}."
    } >&2
    exit 1
fi

echo "check-boundaries.sh: PASS  (${CORE_DIR}/ clean of fastapi|starlette|uvicorn imports)"
