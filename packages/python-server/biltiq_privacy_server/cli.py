# SPDX-License-Identifier: MIT
"""Command-line entry point for the biltiq-privacy server (BILTIQ-013).

``biltiq-privacy-server serve [--host H] [--port P] [--workers N]`` launches
uvicorn against the module-level ASGI app. The app is referenced by *import
string* (:data:`APP_IMPORT_STRING`) rather than imported here, so uvicorn owns
the process lifecycle: with ``--workers > 1`` it forks worker processes, each of
which re-imports the app — re-reading the two secrets (fail-fast, AC5/AC6) and
re-loading the NER model per worker. Passing the live app object instead would
break that multiprocess fork.

stdlib :mod:`argparse` is used on purpose — it keeps the native ``pip install``
path dependency-free (AC8/AC12), so an air-gapped on-prem deployment has no
extra CLI framework to vet.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

#: uvicorn import string for the module-level ASGI app. A string (not the app
#: object) so uvicorn can re-import it in forked workers (AC8).
APP_IMPORT_STRING = "biltiq_privacy_server.app:app"

#: serve defaults — bind-all on 8088, single worker (design § rollout; AC8).
# bind-all is the documented sidecar default; the operator scopes it via firewall/network.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8088
DEFAULT_WORKERS = 1


def build_parser() -> argparse.ArgumentParser:
    """Build the ``biltiq-privacy-server`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="biltiq-privacy-server",
        description="FastAPI sidecar over the biltiq-privacy engine.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="Run the REST server.")
    serve.add_argument(
        "--host", default=DEFAULT_HOST, help="Bind host (default: %(default)s)."
    )
    serve.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Bind port (default: %(default)s)."
    )
    serve.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Worker processes (default: %(default)s).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments and launch the server (console-script entry point)."""
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        uvicorn.run(
            APP_IMPORT_STRING,
            host=args.host,
            port=args.port,
            workers=args.workers,
        )
