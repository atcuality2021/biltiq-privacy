# SPDX-License-Identifier: MIT
"""Tests for ``biltiq_privacy.core.generaliser`` (BILTIQ-008).

Characterization tests porting CDSCO behaviour for the six field
generalisers (AC1), the inject-with-default ``region_map`` seam (AC4), the
framework-free purity invariant (AC3), and per-value irreversibility (AC6).

Golden output strings are hand-derived literals (not recomputed with a copy
of the source regex), so each assertion is a true characterization gate
rather than a circular tautology. All inputs are synthetic, not real PII.
"""
from __future__ import annotations

from pathlib import Path

from biltiq_privacy.core import generaliser


# --- generalise_age (AC1) ---------------------------------------------------

def test_generalise_age_brackets() -> None:
    """Each age maps to its 20-year band, inclusive of both boundaries (AC1)."""
    assert generaliser.generalise_age(35) == "20-39"
    assert generaliser.generalise_age(0) == "0-19"
    assert generaliser.generalise_age(19) == "0-19"
    assert generaliser.generalise_age(20) == "20-39"
    assert generaliser.generalise_age(79) == "60-79"


def test_generalise_age_overflow_floor() -> None:
    """Out-of-range ages fall through to ``"80+"`` — CDSCO quirk, verbatim.

    There is no negative-redaction path: a negative age also returns
    ``"80+"`` because it matches no bracket. This pins the fall-through.
    """
    assert generaliser.generalise_age(80) == "80+"
    assert generaliser.generalise_age(120) == "80+"
    assert generaliser.generalise_age(-5) == "80+"


# --- generalise_date (AC1) --------------------------------------------------

def test_generalise_date_ddmm() -> None:
    """Day is dropped; the middle group is the month (DD/MM ordering)."""
    assert generaliser.generalise_date("15/03/2020") == "March 2020"
    assert generaliser.generalise_date("01-12-1999") == "December 1999"


def test_generalise_date_redacted_fallback() -> None:
    """Unmatched or month-out-of-range input redacts rather than mis-maps.

    ``"05/13/2020"`` documents the DD/MM consequence: the second group (13)
    exceeds 12, so it is redacted, not silently read as a 13th month.
    """
    assert generaliser.generalise_date("not a date") == "[DATE_REDACTED]"
    assert generaliser.generalise_date("05/13/2020") == "[DATE_REDACTED]"


# --- generalise_location + region_map seam (AC1, AC4) -----------------------

def test_generalise_location_known_state() -> None:
    """A substring state match rolls up to its region (AC1)."""
    assert (
        generaliser.generalise_location("AIIMS Delhi")
        == "Healthcare Facility, North India"
    )
    assert (
        generaliser.generalise_location("Kochi, Kerala")
        == "Healthcare Facility, South India"
    )


def test_generalise_location_unknown_fallback() -> None:
    """No matched state -> the exact ``"Healthcare Facility, India"`` fallback."""
    assert generaliser.generalise_location("Somewhere") == "Healthcare Facility, India"


def test_generalise_location_region_map_override() -> None:
    """A custom ``region_map`` overrides the bundled table (AC4 seam).

    The injected map routes its own keys, and the bundled Indian states no
    longer match (e.g. ``"Delhi"`` falls back), proving the default is fully
    replaced rather than merged.
    """
    custom = {"narnia": "Far North"}
    assert (
        generaliser.generalise_location("Narnia clinic", region_map=custom)
        == "Healthcare Facility, Far North"
    )
    assert (
        generaliser.generalise_location("AIIMS Delhi", region_map=custom)
        == "Healthcare Facility, India"
    )


# --- generalise_phone / aadhaar / pan (AC1) ---------------------------------

def test_generalise_phone() -> None:
    """Keep the last 3 digits; sub-threshold input redacts."""
    assert generaliser.generalise_phone("9876543210") == "+91 XXXXX XX210"
    assert generaliser.generalise_phone("12") == "[PHONE_REDACTED]"


def test_generalise_aadhaar() -> None:
    """Keep the last 4 digits; sub-threshold input redacts."""
    assert generaliser.generalise_aadhaar("1234 5678 9012") == "XXXX XXXX 9012"
    assert generaliser.generalise_aadhaar("12") == "[AADHAAR_REDACTED]"


def test_generalise_pan() -> None:
    """Keep the four middle chars of a 10-char PAN; wrong length redacts."""
    assert generaliser.generalise_pan("ABCDE1234F") == "XXXXX1234X"
    assert generaliser.generalise_pan("ABC") == "[PAN_REDACTED]"


# --- irreversibility (AC6) --------------------------------------------------

def test_irreversibility() -> None:
    """The exact input value is not recoverable from the coarsened output.

    Per-value property only: this asserts the generalised form does not
    contain the full original value — it is NOT a dataset-level k-anonymity
    guarantee (see module docstring; measurement is BILTIQ-021).
    """
    assert "35" not in generaliser.generalise_age(35)
    assert "9876543210" not in generaliser.generalise_phone("9876543210")
    assert "123456789012" not in generaliser.generalise_aadhaar("1234 5678 9012")
    assert "ABCDE1234F" not in generaliser.generalise_pan("ABCDE1234F")


# --- purity invariant (AC3) -------------------------------------------------

def test_module_is_pure() -> None:
    """Module imports only stdlib — no config/DB/framework/LLM coupling (AC3).

    Static source assertion mirroring BILTIQ-007's
    ``test_no_settings_or_env_import``: ``mypy`` does not verify import
    provenance, so this guards the framework-free invariant against future
    refactors. Matches call/attribute/import forms, not prose, since the
    docstring legitimately discusses k-anonymity and regions.
    """
    source = Path(generaliser.__file__).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "import settings" not in source
    assert "from backend" not in source
    assert "import fastapi" not in source
    assert "import pydantic" not in source
    assert "sqlalchemy" not in source
