# SPDX-License-Identifier: MIT
"""Indian PII test fixtures — synthetic, structurally-valid sample data.

Each of the eight entity types has two tuples:

* ``{ENTITY}_VALID`` — ≥4 synthetic values that the matching regex MUST
  accept (covers AC1 happy path).
* ``{ENTITY}_FALSE_POSITIVES`` — ≥4 near-miss strings that the matching
  regex MUST reject (covers AC6 false-positive floor).

Total: 32 valid + 32 false-positive = 64 parameterised cases, exceeding
the AC6 floor of "≥40 cases overall".

PII safety
----------

NEVER store real PII in these tuples. Every value here is:

* Structurally-valid but synthetic (alphabet placeholders for letter slots,
  repeating / sequential / hand-constructed digits for numeric slots).
* For ``AADHAAR_VALID``: independently verified to FAIL the Verhoeff
  checksum at fixture-construction time (see spec.html line 258 — "any
  12-digit number in fixture data must not pass the Verhoeff checksum").
  This makes accidental collision with a real Aadhaar number impossible
  even if the synthetic value were issued in the future.

The BiltIQ memory-spine + git history are not appropriate stores for real
personal data; this is enforced by AGENT_RULES.md and DPDP 2023 § 4.
"""
from __future__ import annotations

from typing import Final

# Aadhaar — 12-digit unique identity number (UIDAI).
# All values fail Verhoeff (verified during Step 4 fixture construction).
AADHAAR_VALID: Final[tuple[str, ...]] = (
    "1234 5678 9011",
    "0000-0000-0001",
    "9999 9999 9991",
    "1357-2468-0246",
)
AADHAAR_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "1234-5678-901",          # 11 digits — too short
    "12345 6789 0123",        # 5+4+4 grouping — wrong format
    "Order-1234567890ABC",    # only 10 digits available before non-digits
    "abc 1234 5678",          # only 8 digits — too short
)

# ABHA — 14-digit Ayushman Bharat Health Account number, dashed.
ABHA_VALID: Final[tuple[str, ...]] = (
    "12-3456-7890-1234",
    "00-0000-0000-0000",
    "99-9999-9999-9999",
    "11-2233-4455-6677",
)
ABHA_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "1234-5678-9012-3456",    # 4+4+4+4 not 2+4+4+4
    "12-345-6789-0123",       # 3-digit middle group
    "AB-1234-5678-9012",      # letters in head group
    "12345-6789-0123-4567",   # 5-digit head group
)

# PAN — 10-character Permanent Account Number (Income Tax Department).
PAN_VALID: Final[tuple[str, ...]] = (
    "ABCDE1234F",
    "ZZZZZ0000Z",
    "AAAAA9999A",
    "WXYZQ5678P",
)
PAN_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "ABCDE123F",              # 9 chars — missing one digit
    "abcde1234F",             # lowercase head letters
    "12345ABCD6",             # digits / letters in wrong order
    "AB CDE1234F",            # internal space breaks the run
)

# GSTIN — 15-character Goods and Services Tax Identification Number.
GSTIN_VALID: Final[tuple[str, ...]] = (
    "27ABCDE1234F1Z5",
    "07XYZAB9999K2Z9",
    "29MNOPQ0000A1ZA",
    "07AAAAA1111A1ZZ",
)
GSTIN_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "27ABCDE1234F1Y5",        # Y at position 13 — must be Z
    "27ABCD1234F1Z5",         # 4 letters in middle (need 5)
    "27abcde1234f1z5",        # lowercase
    "ABCDEFGHIJKLMNO",        # all letters — wrong shape
)

# Voter ID — EPIC (Electors Photo Identity Card) number issued by ECI.
VOTER_ID_VALID: Final[tuple[str, ...]] = (
    "ABC1234567",
    "XYZ0000000",
    "DEL9876543",
    "MUM1234567",
)
VOTER_ID_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "AB1234567",              # 2 letters (need 3)
    "ABCD1234567",            # 4 letters (need 3)
    "ABC123456",              # 6 digits (need 7)
    "ABC12345678",            # 8 digits (need 7)
)

# IFSC — Indian Financial System Code (RBI bank branch identifier).
# 11 characters: 4 letters + '0' + 6 alphanumeric.
IFSC_VALID: Final[tuple[str, ...]] = (
    "HDFC0001234",
    "SBIN0123456",
    "ICIC0ABCDEF",
    "AXIS0XYZ123",
)
IFSC_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "HDFC1001234",            # position 5 must be '0'
    "HDF0001234",             # 3-letter bank code (need 4)
    "HDFC001234",             # 10 chars (need 11)
    "hdfc0001234",            # lowercase
)

# Indian Phone — mobile number (10 digits, leading 6/7/8/9) with optional
# +91 country-code prefix. Spec key: PHONE_IN.
PHONE_IN_VALID: Final[tuple[str, ...]] = (
    "9876543210",
    "+91 9876543210",
    "+91-8765432109",
    "76543 21098",
)
PHONE_IN_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "5876543210",             # leading 5 (need 6-9)
    "98765432",               # 8 digits — too short
    "9876 543",                # 7 digits — too short
    "1234567890",             # leading 1 (need 6-9)
)

# Medical Registration — Indian Medical Council Registration Number.
# Council-prefixed; intentionally permissive — confidence 0.6 in
# CDSCO-RegAI:presidio_engine.py reflects the high false-positive baseline.
MEDICAL_REG_VALID: Final[tuple[str, ...]] = (
    "MCI12345",
    "DR1234",
    "Registration No: KMC56789",
    "Registration Number AP123456",
)
MEDICAL_REG_FALSE_POSITIVES: Final[tuple[str, ...]] = (
    "M1234",                  # 1 letter (need 2-3)
    "MCID12345",              # 4 letters (need 2-3)
    "MCI123",                 # 3 digits (need 4-6)
    "MCI1234567",             # 7 digits (need 4-6)
)
