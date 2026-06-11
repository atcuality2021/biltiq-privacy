# SPDX-License-Identifier: MIT
"""Backup encryption helpers (age-binary subprocess wrappers, from v0.5.0).

BILTIQ-004 lands the streaming wrapper (open_age_writer / open_age_reader)
backed by the system age binary. See age_stream module docstring and
docs/adr/0003-age-streaming-pattern.md.
"""
from __future__ import annotations

from .age_stream import (
    AgeNotInstalledError,
    AgeProcessError,
    open_age_reader,
    open_age_writer,
)

__all__ = [
    "AgeNotInstalledError",
    "AgeProcessError",
    "open_age_reader",
    "open_age_writer",
]
