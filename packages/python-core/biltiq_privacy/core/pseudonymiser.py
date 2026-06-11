# SPDX-License-Identifier: MIT
"""Entity → token pseudonymisation.

Ports the CDSCO-RegAI ``backend/modules/anonymisation/pseudonymiser.py``
logic (``make_token`` + ``pseudonymise_text``) into a key-bound
``Pseudonymiser`` class. There is no runtime dependency on CDSCO-RegAI.

The behavioural change from CDSCO is that the HMAC key is injected once,
into ``__init__`` (keyword-only), rather than read from a global
``settings`` object. The key is validated at construction time — an empty
key raises :class:`HMACKeyRequiredError` before any text is processed
(``overview.md`` failure-mode contract / spec AC4). The token form
``[TYPE_<hex>]``, the end-to-start replacement order, and the restored
audit ordering are preserved verbatim from CDSCO so behaviour does not
drift (spec AC5).
"""
from __future__ import annotations

from typing import TypedDict

from biltiq_privacy.core.doc_hasher import _normalise_key, hmac_pseudonymise
from biltiq_privacy.core.exceptions import HMACKeyRequiredError


class Detection(TypedDict):
    """A single detected PII span. Mirrors the CDSCO detection dict shape."""

    entity_type: str
    text: str
    start: int
    end: int
    score: float


class AuditRecord(TypedDict):
    """One audit row per replaced span. Keys preserved verbatim from CDSCO."""

    entity_type: str
    pseudonym_token: str
    position_start: int
    position_end: int
    confidence: float


class Pseudonymiser:
    """Deterministic HMAC pseudonymiser bound to a single key.

    The key is injected once and held on the instance, so callers do not
    thread it through every call (and cannot pass an inconsistent key
    mid-document). Tokens are deterministic per key: the same
    ``(entity_type, value, key)`` always yields the same token; a different
    key yields a different token.
    """

    def __init__(self, *, key: bytes | str) -> None:
        """Bind and validate the HMAC ``key`` (keyword-only).

        Raises:
            HMACKeyRequiredError: if ``key`` normalises to empty bytes. The
                check runs here, before any text is processed (AC4).
        """
        normalised = _normalise_key(key)
        if not normalised:
            raise HMACKeyRequiredError(
                "Pseudonymiser requires a non-empty HMAC key"
            )
        self._key = normalised

    def make_token(
        self, entity_type: str, value: str, *, token_length: int = 8
    ) -> str:
        """Return a stable ``[TYPE_<hex>]`` token for ``value``.

        ``token_length`` is the number of leading hex characters of the
        HMAC-SHA256 digest to keep (default ``8`` = 32 bits, the
        CDSCO-equivalent width). Widen it for high-volume corpora: at the
        default, the birthday bound puts a ~50% collision probability near
        ~2**16 distinct values. A re-identification vault is out of scope —
        tokens are forward-only.
        """
        digest = hmac_pseudonymise(value, key=self._key)
        return f"[{entity_type}_{digest[:token_length]}]"

    def pseudonymise_text(
        self, text: str, detections: list[Detection]
    ) -> tuple[str, list[AuditRecord]]:
        """Replace detected PII spans with deterministic HMAC tokens.

        Returns ``(anonymised_text, audit_records)``. Spans are replaced
        from end-of-string backwards so earlier offsets stay valid as the
        string is rebuilt; the audit list is then reversed to restore the
        original document order (CDSCO algorithm preserved).
        """
        sorted_dets = sorted(detections, key=lambda d: d["start"], reverse=True)
        result = text
        audit: list[AuditRecord] = []

        for det in sorted_dets:
            token = self.make_token(det["entity_type"], det["text"])
            result = result[: det["start"]] + token + result[det["end"] :]
            audit.append(
                AuditRecord(
                    entity_type=det["entity_type"],
                    pseudonym_token=token,
                    position_start=det["start"],
                    position_end=det["end"],
                    confidence=det["score"],
                )
            )

        audit.reverse()  # restore original document order
        return result, audit
