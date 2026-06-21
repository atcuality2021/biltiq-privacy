# SPDX-License-Identifier: MIT
"""POST /validate — attest a prior anonymisation against a regime (BILTIQ-013, AC3).

Translate-and-delegate: the handler resolves the named regime (unknown id ->
:class:`~biltiq_privacy_server.errors.UnknownRegimeError` -> HTTP 422), rebuilds
the library ``Detection`` / ``AuditRecord`` TypedDicts from the validated wire
models, and calls ``regime.validate(...)`` once, returning the
:class:`~biltiq_privacy.ComplianceReport` as the response. No compliance logic
lives here.

The wire models are rebuilt into the library TypedDicts field-by-field (rather
than ``model_dump()``) so the call stays strictly typed under ``mypy --strict``:
``model_dump()`` would yield ``dict[str, Any]``, which is not assignable to
``Sequence[Detection]``.

``generated_at`` defaults through :func:`server_now_iso` when the client omits
it; the report echoes whatever timestamp it attests under. Plain ``def`` (alt
#7). The router-level dependencies enforce both the JWT (AC5) and — per AC7's
"all three data endpoints return 503" — engine readiness, even though the
validation logic itself does not touch the detector: ``get_detector`` runs only
for its degraded-state side effect and its return value is discarded.
"""
from __future__ import annotations

from biltiq_privacy.core.pseudonymiser import AuditRecord, Detection
from fastapi import APIRouter, Depends

from biltiq_privacy_server.dependencies import get_detector, require_jwt
from biltiq_privacy_server.models import ValidateRequest, ValidateResponse
from biltiq_privacy_server.regimes_registry import resolve_regime
from biltiq_privacy_server.routers import server_now_iso

router = APIRouter(dependencies=[Depends(require_jwt), Depends(get_detector)])


@router.post("/validate", response_model=ValidateResponse)
def validate(body: ValidateRequest) -> ValidateResponse:
    """Validate a prior anonymisation outcome against the named regime (AC3)."""
    regime = resolve_regime(body.regime)
    generated_at = (
        body.generated_at if body.generated_at is not None else server_now_iso()
    )

    detections = [
        Detection(
            entity_type=d.entity_type,
            text=d.text,
            start=d.start,
            end=d.end,
            score=d.score,
        )
        for d in body.detections
    ]
    audit_records = [
        AuditRecord(
            entity_type=r.entity_type,
            pseudonym_token=r.pseudonym_token,
            position_start=r.position_start,
            position_end=r.position_end,
            confidence=r.confidence,
        )
        for r in body.audit_records
    ]

    report = regime.validate(
        body.original_text,
        body.anonymised_text,
        detections,
        audit_records,
        generated_at=generated_at,
    )
    return ValidateResponse.model_validate(report)
