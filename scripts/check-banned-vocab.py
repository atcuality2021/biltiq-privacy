#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Filter grep hits to find real banned-vocab usage (not rule listings).

Reads `path:lineno:content` lines from stdin (the output of `grep -niE` on
the banned-vocab regex) and emits only the lines that look like real prose
usage. Suppresses rule-definition references, multi-term listings, and
bulleted single-word listings so AGENT_RULES.md, CHEATSHEET.md, and similar
rule files don't trigger the gate.

Exits 0 with the filtered lines on stdout (empty stdout = no violations).
Used by .github/workflows/biltiq-gates.yml banned-vocab job.

The job in CI does the grep and pipes hits in; this script does the rule
filtering. Splitting it out keeps the workflow YAML free of nested-escape
heredoc soup that GitHub Actions' workflow validator rejects at parse time.
"""

from __future__ import annotations

import re
import sys

BANNED = ["cutting-edge", "revolutionary", "empowering", "seamless", "future-ready"]
BANNED_RE = "|".join(BANNED)
RULE_CONTEXT_MARKERS = (
    "banned",
    "do not use",
    "no marketing",
    "use plain",
    "enforced",
    "flag",
)
SINGLE_WORD_LISTING_RE = re.compile(
    rf"^[-*\s]*['\"`]?({BANNED_RE})['\"`]?\s*\.?\s*$",
    re.IGNORECASE,
)


def is_violation(line: str) -> bool:
    line_lower = line.lower()
    if sum(1 for w in BANNED if w in line_lower) >= 2:
        return False
    if any(marker in line_lower for marker in RULE_CONTEXT_MARKERS):
        return False
    parts = line.split(":", 2)
    body = parts[2].strip() if len(parts) >= 3 else line.strip()
    if SINGLE_WORD_LISTING_RE.match(body):
        return False
    return True


def main() -> int:
    violations = [line.rstrip() for line in sys.stdin if is_violation(line)]
    if violations:
        print("\n".join(violations))
    return 0


def self_test() -> int:
    """Run a small set of in-process cases. Prints PASS/FAIL per case; exits 1 on any failure.

    Invoked as: python3 scripts/check-banned-vocab.py --self-test
    Used as a local sanity check and as a pre-step in the CI banned-vocab job.
    """
    cases: list[tuple[str, str, bool]] = [
        # (label, grep-shaped line, expected is_violation)
        ("real prose use", "docs/marketing.md:14:Our seamless integration solves all your problems.", True),
        ("rule-listing single word (bulleted)", 'AGENT_RULES.md:42:- "seamless"', False),
        ("rule-context marker 'banned'", "AGENT_RULES.md:30:The following words are banned: seamless, revolutionary.", False),
        ("multi-term listing (2+ banned words)", "CHEATSHEET.md:8:cutting-edge revolutionary empowering — none of these.", False),
        ("rule-context marker 'do not use'", "AGENT_RULES.md:55:Do not use 'cutting-edge' in any copy.", False),
        ("real prose use, different word", "blog/post.md:3:This is a revolutionary approach.", True),
        ("quoted single word listing", 'README.md:99:- `cutting-edge`', False),
    ]
    failures = 0
    for label, line, expected in cases:
        actual = is_violation(line)
        ok = actual == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: expected={expected} actual={actual}")
        if not ok:
            failures += 1
    print(f"check-banned-vocab.py self-test: {len(cases) - failures}/{len(cases)} pass")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        sys.exit(self_test())
    sys.exit(main())
