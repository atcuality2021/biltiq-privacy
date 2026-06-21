# SPDX-License-Identifier: MIT
"""POST /anonymize — full anonymisation + audit row (BILTIQ-013, AC2/AC6).

Translate-and-delegate: the handler fills the two server-owned defaults
(``generated_at`` from :func:`server_now_iso`, ``prev_hash`` from
``GENESIS_PREV_HASH``), resolves an optional regime, then calls the
:func:`biltiq_privacy.anonymise` facade *once* and serialises its
:class:`~biltiq_privacy.AnonymiseResult` into the wire response. It never
re-chains the underlying wrappers (the thin-shim contract) and re-derives no
privacy logic.

The HMAC pseudonymisation key arrives **only** through ``Depends(get_hmac_key)``
— never a body field, never echoed into the response, never logged (AC6). The
original text is likewise not echoed back: the library drops it to narrow the
PII surface and the response model follows.

Plain ``def`` so the synchronous pipeline runs in the threadpool (alt #7);
JWT- and engine-readiness-gated at router level (AC5/AC7).
"""
from __future__ import annotations

from typing import Annotated

from biltiq_privacy import GENESIS_PREV_HASH, Detector, Regime, anonymise
from fastapi import APIRouter, Depends

from biltiq_privacy_server.dependencies import get_detector, get_hmac_key, require_jwt
from biltiq_privacy_server.models import (
    AnonymizeRequest,
    AnonymizeResponse,
    AuditRecordModel,
    AuditRowModel,
    ComplianceReportModel,
    DetectionModel,
)
from biltiq_privacy_server.regimes_registry import resolve_regime
from biltiq_privacy_server.routers import server_now_iso

router = APIRouter(dependencies=[Depends(require_jwt)])


@router.post("/anonymize", response_model=AnonymizeResponse)
def anonymize(
    body: AnonymizeRequest,
    detector: Annotated[Detector, Depends(get_detector)],
    hmac_key: Annotated[bytes, Depends(get_hmac_key)],
) -> AnonymizeResponse:
    """Anonymise ``body.text`` end to end and serialise the result (AC2)."""
    generated_at = (
        body.generated_at if body.generated_at is not None else server_now_iso()
    )
    prev_hash = body.prev_hash if body.prev_hash is not None else GENESIS_PREV_HASH
    regime: Regime | None = (
        resolve_regime(body.regime) if body.regime is not None else None
    )

    result = anonymise(
        body.text,
        detector=detector,
        key=hmac_key,
        generated_at=generated_at,
        regime=regime,
        generalise=body.generalise,
        prev_hash=prev_hash,
    )

    return AnonymizeResponse(
        anonymised_text=result.anonymised_text,
        detections=[DetectionModel.model_validate(d) for d in result.detections],
        audit_records=[
            AuditRecordModel.model_validate(r) for r in result.audit_records
        ],
        audit_row=AuditRowModel.model_validate(result.audit_row),
        compliance=(
            ComplianceReportModel.model_validate(result.compliance)
            if result.compliance is not None
            else None
        ),
    )
