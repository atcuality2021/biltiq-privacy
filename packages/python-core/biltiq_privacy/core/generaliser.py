# SPDX-License-Identifier: MIT
"""Rule-based generalisation primitives for the privacy engine.

Ported from the CDSCO-RegAI internal codebase
(``backend/modules/anonymisation/generaliser.py``) as a productisation step
for the OSS ``biltiq-privacy`` SDK. There is no runtime dependency on
CDSCO-RegAI.

These functions coarsen quasi-identifiers *after* pseudonymisation — exact
age to a 20-year bracket, exact date to month/year, precise location to a
region rollup, and Indian ID/phone numbers to masked suffixes. The rules are
India-centric by default (state-to-region map, Aadhaar/PAN/phone formats); a
caller may inject a different ``region_map`` without editing this module
(full region-pack loading is deferred to a later phase).

This is **rule-based generalisation, NOT a dataset-level k-anonymity
guarantee.** Each function coarsens a single value; it does not measure or
enforce that the resulting dataset satisfies k-anonymity / l-diversity /
t-closeness. Dataset-level measurement is a separate concern (BILTIQ-021).
Do not represent the output of these functions as a k-anonymity guarantee.

The only behavioural change from the CDSCO original is the decoupling of the
region table: ``generalise_location`` takes an optional keyword-only
``region_map`` that defaults to the bundled Indian table. The match logic,
output formats, and redaction fallbacks are preserved verbatim.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypedDict

# 20-year brackets for improved k-anonymity (k >= 2 target). Ported verbatim.
_AGE_BRACKETS = [
    (0, 19), (20, 39), (40, 59), (60, 79),
]

# Default Indian state -> region rollup. A caller may override via the
# ``region_map`` keyword on ``generalise_location`` (inject-with-default seam).
_REGION_MAP = {
    "delhi": "North India",
    "uttar pradesh": "North India",
    "punjab": "North India",
    "haryana": "North India",
    "rajasthan": "North India",
    "chandigarh": "North India",
    "maharashtra": "West India",
    "gujarat": "West India",
    "goa": "West India",
    "tamil nadu": "South India",
    "karnataka": "South India",
    "kerala": "South India",
    "andhra pradesh": "South India",
    "telangana": "South India",
    "puducherry": "South India",
    "west bengal": "East India",
    "odisha": "East India",
    "bihar": "East India",
    "jharkhand": "East India",
    "madhya pradesh": "Central India",
    "chhattisgarh": "Central India",
}


def generalise_age(age: int) -> str:
    """Return the 20-year bracket label for ``age``.

    ``35`` -> ``"20-39"``. Any value outside the defined bands (including a
    value above 79 or a negative age) falls through to ``"80+"`` — the
    CDSCO behaviour, preserved verbatim.
    """
    for lo, hi in _AGE_BRACKETS:
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return "80+"


def generalise_date(date_str: str) -> str:
    """Return ``"Month YYYY"`` for a ``DD/MM/YYYY`` (or ``DD-MM-YYYY``) date.

    The day is discarded; only month and year survive. The middle group is
    read as the **month**, i.e. the input is assumed to be in day/month/year
    order (the India-centric default). An input in month/day order whose
    second group exceeds 12 — or any string that does not match the pattern —
    returns ``"[DATE_REDACTED]"`` rather than being mis-mapped.
    """
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", date_str)
    if m:
        months = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        month_num = int(m.group(2))
        if 1 <= month_num <= 12:
            return f"{months[month_num]} {m.group(3)}"
    return "[DATE_REDACTED]"


def generalise_location(
    location: str, *, region_map: dict[str, str] | None = None
) -> str:
    """Return ``"Healthcare Facility, <region>"`` for a known location.

    ``location`` is lower-cased and tested for each key of the region table as
    a substring; the first match wins. Falls back to
    ``"Healthcare Facility, India"`` when no key matches. ``region_map`` is
    keyword-only and defaults to the bundled Indian state-to-region table
    (``_REGION_MAP``); pass a different mapping to override without editing
    this module (inject-with-default seam).
    """
    table = _REGION_MAP if region_map is None else region_map
    lower = location.lower()
    for state, region in table.items():
        if state in lower:
            return f"Healthcare Facility, {region}"
    return "Healthcare Facility, India"


def generalise_phone(phone: str) -> str:
    """Mask a phone number to ``"+91 XXXXX XX<last3>"`` keeping the last 3 digits.

    Non-digit characters are stripped first. Inputs with fewer than 3 digits
    return ``"[PHONE_REDACTED]"``.
    """
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 3:
        return f"+91 XXXXX XX{digits[-3:]}"
    return "[PHONE_REDACTED]"


def generalise_aadhaar(aadhaar: str) -> str:
    """Mask an Aadhaar number to ``"XXXX XXXX <last4>"`` keeping the last 4 digits.

    Non-digit characters are stripped first. Inputs with fewer than 4 digits
    return ``"[AADHAAR_REDACTED]"``.
    """
    digits = re.sub(r"\D", "", aadhaar)
    if len(digits) >= 4:
        return f"XXXX XXXX {digits[-4:]}"
    return "[AADHAAR_REDACTED]"


def generalise_pan(pan: str) -> str:
    """Mask a PAN to ``"XXXXX<chars 6-9>X"`` keeping the four middle characters.

    Whitespace is stripped first; the input must be exactly 10 characters
    after stripping, otherwise ``"[PAN_REDACTED]"`` is returned.
    """
    clean = re.sub(r"\s", "", pan)
    if len(clean) == 10:
        return f"XXXXX{clean[5:9]}X"
    return "[PAN_REDACTED]"


class GeneralisationSpan(TypedDict):
    """One detected span to generalise within already-pseudonymised text.

    The orchestrator (BILTIQ-012) assembles this from BILTIQ-007's
    ``Detection`` (carries ``entity_type`` + ``text``) and ``AuditRecord``
    (carries ``pseudonym_token``); neither shipped type carries all three
    fields, so this is a fresh input shape rather than an edit to either.

    - ``entity_type``: the recogniser label, routed through ``_GENERALISER``.
    - ``text``: the original detected value, fed to the per-entity generaliser.
    - ``pseudonym_token``: the token currently standing in for the value in
      the text; it is what gets replaced with the generalised value.
    """

    entity_type: str
    text: str
    pseudonym_token: str


# Entity types whose generaliser accepts the injected ``region_map``. Kept
# separate from ``_GENERALISER`` so the field functions need no unused kwarg.
_LOCATION_ENTITY_TYPES = frozenset({"LOCATION", "ADDRESS", "HOSPITAL"})

# Entity-type -> generaliser dispatch table. Ported verbatim from CDSCO; the
# seven keys are load-bearing for downstream routing. Do not add or drop keys
# without a spec change (there is no ABHA generaliser).
_GENERALISER: dict[str, Callable[[str], str]] = {
    "IN_AADHAAR": generalise_aadhaar,
    "IN_PAN": generalise_pan,
    "IN_PHONE": generalise_phone,
    "PHONE_NUMBER": generalise_phone,
    "LOCATION": generalise_location,
    "ADDRESS": generalise_location,
    "HOSPITAL": generalise_location,
}


def generalise_text(
    pseudonymised_text: str,
    spans: list[GeneralisationSpan],
    *,
    region_map: dict[str, str] | None = None,
) -> str:
    """Apply irreversible generalisation to already-pseudonymised text.

    For each span whose ``entity_type`` has a generalisation function, the
    span's ``pseudonym_token`` is replaced — once — with the generalised value
    derived from the span's ``text``. Spans with an unknown ``entity_type``, or
    whose token is absent from the text, are left untouched. ``region_map`` is
    threaded into the location-family generalisers only (others take no such
    argument); it defaults to the bundled Indian table.

    This is rule-based, per-value generalisation — NOT a dataset-level
    k-anonymity guarantee (see the module docstring; measurement is
    BILTIQ-021).
    """
    result = pseudonymised_text
    for span in spans:
        entity_type = span["entity_type"]
        fn = _GENERALISER.get(entity_type)
        if fn is None:
            continue
        token = span["pseudonym_token"]
        if token and token in result:
            if entity_type in _LOCATION_ENTITY_TYPES:
                generalised = generalise_location(span["text"], region_map=region_map)
            else:
                generalised = fn(span["text"])
            result = result.replace(token, generalised, 1)
    return result
