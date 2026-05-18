# SPDX-License-Identifier: MIT
"""Indian PII test fixtures — empty tuples awaiting dev-supplied values.

The eight entity types match the design.html § Eight Entity Types list and
are referenced by name from ``tests/indian/test_patterns.py``. Each entity
has two tuples:

* ``{ENTITY}_VALID`` — known-valid (synthetic, real-shaped) PII values that
  the matching regex MUST accept. Per AC6 floor, ≥4 values per entity once
  populated in step 4.
* ``{ENTITY}_FALSE_POSITIVES`` — near-miss strings that the matching regex
  MUST reject. ≥1 value per entity once populated.

Tuples are kept empty at this commit (step 2). They are filled in step 4
together with the regex strings — that pairing is intentional: the regex
and the fixtures are co-designed and land in one logical commit (DEV
PASTE step).

NEVER store real PII in these tuples — only synthetic / structurally-valid
values. The BiltIQ memory-spine + git history are not appropriate stores
for real personal data.
"""
from __future__ import annotations

from typing import Final

# Aadhaar — 12-digit unique identity number (UIDAI).
AADHAAR_VALID: Final[tuple[str, ...]] = ()
AADHAAR_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# ABHA — 14-digit Ayushman Bharat Health Account number.
ABHA_VALID: Final[tuple[str, ...]] = ()
ABHA_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# PAN — 10-character Permanent Account Number (Income Tax Department).
PAN_VALID: Final[tuple[str, ...]] = ()
PAN_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# GSTIN — 15-character Goods and Services Tax Identification Number.
GSTIN_VALID: Final[tuple[str, ...]] = ()
GSTIN_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# Voter ID — EPIC (Electors Photo Identity Card) number issued by ECI.
VOTER_ID_VALID: Final[tuple[str, ...]] = ()
VOTER_ID_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# Driving Licence — state-prefixed licence number issued by RTOs.
DRIVING_LICENSE_VALID: Final[tuple[str, ...]] = ()
DRIVING_LICENSE_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# Indian Passport — passport number issued by MEA Passport Seva.
INDIAN_PASSPORT_VALID: Final[tuple[str, ...]] = ()
INDIAN_PASSPORT_FALSE_POSITIVES: Final[tuple[str, ...]] = ()

# Indian Phone — mobile number (10 digits, leading 6/7/8/9) with optional
# country-code prefix.
INDIAN_PHONE_VALID: Final[tuple[str, ...]] = ()
INDIAN_PHONE_FALSE_POSITIVES: Final[tuple[str, ...]] = ()
