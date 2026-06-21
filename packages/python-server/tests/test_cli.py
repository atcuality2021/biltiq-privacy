# SPDX-License-Identifier: MIT
"""CLI / console-script entry-point tests (BILTIQ-013, AC8).

Asserts argument parsing and the uvicorn launch contract only — ``uvicorn.run``
is monkeypatched in every test, so no socket is ever bound. The ``python -m``
delegation is exercised via :func:`runpy.run_module` with a patched ``main``.
"""
from __future__ import annotations

import runpy

import pytest

from biltiq_privacy_server.cli import APP_IMPORT_STRING, main


def test_serve_parses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """No flags -> host 0.0.0.0, port 8088, 1 worker; app passed by import string (AC8)."""
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr("biltiq_privacy_server.cli.uvicorn.run", fake_run)
    main(["serve"])

    assert captured["app"] == APP_IMPORT_STRING == "biltiq_privacy_server.app:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8088
    assert captured["workers"] == 1


def test_serve_overrides_host_port_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """--host/--port/--workers flags propagate to uvicorn.run (AC8)."""
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr("biltiq_privacy_server.cli.uvicorn.run", fake_run)
    main(["serve", "--host", "127.0.0.1", "--port", "9090", "--workers", "4"])

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9090
    assert captured["workers"] == 4


def test_invalid_port_exits_nonzero() -> None:
    """A non-integer --port is rejected by argparse with a non-zero exit (AC8)."""
    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--port", "not-a-number"])
    assert exc_info.value.code != 0


def test_missing_subcommand_exits_nonzero() -> None:
    """No subcommand is rejected (the subparser is required) (AC8)."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_module_entrypoint_calls_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m biltiq_privacy_server` delegates to cli.main (AC8)."""
    called: dict[str, object] = {}

    def fake_main(argv: object = None) -> None:
        called["argv"] = argv

    # __main__ does `from biltiq_privacy_server.cli import main`, so patching the
    # attribute on the cli module makes the fresh import resolve to fake_main.
    monkeypatch.setattr("biltiq_privacy_server.cli.main", fake_main)
    monkeypatch.setattr("sys.argv", ["biltiq-privacy-server", "serve"])

    runpy.run_module("biltiq_privacy_server", run_name="__main__")

    assert "argv" in called
