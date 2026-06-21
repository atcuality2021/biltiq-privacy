# SPDX-License-Identifier: MIT
"""Endpoint routers + the server's single wall-clock read (BILTIQ-013).

Each sibling module defines exactly one :class:`~fastapi.APIRouter`; the factory
(:func:`biltiq_privacy_server.app.create_app`) includes them. The three data
routers (``detect``, ``anonymize``, ``validate``) declare their gate
dependencies at *router* level so authentication (and, per AC7, engine
readiness) cannot be forgotten on an individual route (design alternative #5);
``health`` declares none — ``/healthz`` is unauthenticated (AC4).

:func:`server_now_iso` is the **only** place the server reads the wall clock
(dev ruling). The library is clock-free by contract: it echoes a caller-supplied
``generated_at`` verbatim so identical inputs stay reproducible. The server, as
the system boundary, therefore originates the timestamp here and nowhere else;
``/anonymize`` and ``/validate`` both default a missing ``generated_at`` through
this one helper, which keeps the clock read auditable and monkeypatchable in
tests. Defining it here (not in a router module) keeps the import graph acyclic:
the router modules import *from* this package init, which imports only the
standard library.
"""
from __future__ import annotations

from datetime import UTC, datetime


def server_now_iso() -> str:
    """Return the current UTC instant as an ISO-8601 string (the one clock read).

    Timezone-aware (``UTC``) so the emitted timestamp is unambiguous and the
    value round-trips through the audit chain unchanged.
    """
    return datetime.now(UTC).isoformat()
