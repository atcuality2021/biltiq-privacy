# SPDX-License-Identifier: MIT
"""``python -m biltiq_privacy_server`` → the CLI entry point (BILTIQ-013).

Delegates to :func:`biltiq_privacy_server.cli.main`, giving the module-execution
path parity with the ``biltiq-privacy-server`` console script.
"""
from __future__ import annotations

from biltiq_privacy_server.cli import main

if __name__ == "__main__":
    main()
