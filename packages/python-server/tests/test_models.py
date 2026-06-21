# SPDX-License-Identifier: MIT
"""Wire-model + regime-registry unit tests (BILTIQ-013, AC1/AC3).

Two jobs:

* prove each pydantic wire model validates straight from the authoritative
  library type (TypedDict dict or frozen dataclass), and
* a **field-name drift guard** — assert the model's fields equal the library
  type's keys, so a future change to a library record that the wire model does
  not mirror fails here (the design's "thin-shim watch") rather than silently
  dropping a field on the wire.
"""
from __future__ import annotations

import dataclasses

import pytest
from biltiq_privacy import (
    AuditRecord,
    ChainedRow,
    ComplianceCheck,
    ComplianceReport,
    DetectedEntity,
    DPDPRegime,
    Regime,
)
from pydantic import BaseModel

from biltiq_privacy_server.errors import UnknownRegimeError
from biltiq_privacy_server.models import (
    AnonymizeRequest,
    AnonymizeResponse,
    AuditRecordModel,
    AuditRowModel,
    ComplianceReportModel,
    DetectionModel,
    DetectRequest,
    DetectResponse,
    ErrorResponse,
    HealthResponse,
    ValidateRequest,
    ValidateResponse,
)
from biltiq_privacy_server.regimes_registry import resolve_regime


def _typed_dict_keys(td: type) -> set[str]:
    """All keys of a ``TypedDict`` type, including inherited ones."""
    return set(td.__required_keys__) | set(td.__optional_keys__)


def _dataclass_fields(dc: type) -> set[str]:
    """Stored field names of a dataclass (excludes ``@property`` derivations)."""
    return {f.name for f in dataclasses.fields(dc)}


def test_detection_model_validates_from_typeddict() -> None:
    """A DetectedEntity dict round-trips through model_validate (AC1)."""
    entity: DetectedEntity = {
        "entity_type": "PHONE_NUMBER",
        "text": "9876543210",
        "start": 8,
        "end": 18,
        "score": 0.85,
        "source": "presidio",
    }
    model = DetectionModel.model_validate(entity)
    assert model.model_dump() == entity


def test_audit_record_and_row_models_mirror_library_keys() -> None:
    """Drift guard: each element model's fields == the library type's keys."""
    assert set(DetectionModel.model_fields) == _typed_dict_keys(DetectedEntity)
    assert set(AuditRecordModel.model_fields) == _typed_dict_keys(AuditRecord)
    assert set(AuditRowModel.model_fields) == _typed_dict_keys(ChainedRow)
    assert set(ComplianceReportModel.model_fields) == (
        _dataclass_fields(ComplianceReport) | {"score"}
    )


def _sample_report() -> ComplianceReport:
    """A real ComplianceReport with one passing check (7/8)."""
    check = ComplianceCheck(
        check_id="DPDP-1",
        name="PII Removal Completeness",
        description="All detected PII is replaced.",
        status="pass",
        details="8 of 8 spans replaced.",
        section="Section 8(1) — Data Minimisation",
    )
    return ComplianceReport(
        regime_id="DPDP-2023",
        compliant=True,
        passed=7,
        total=8,
        checks=(check,),
        generated_at="2026-06-21T00:00:00+00:00",
        frameworks=("DPDP Act 2023",),
    )


def test_compliance_report_model_includes_score() -> None:
    """The derived score @property is echoed into the model (AC3)."""
    model = ComplianceReportModel.model_validate(_sample_report())
    assert model.score == "7/8"
    assert model.compliant is True
    assert model.checks[0].check_id == "DPDP-1"


def test_validate_response_is_full_report_shape() -> None:
    """ValidateResponse carries every report field incl. score (AC3)."""
    payload = ValidateResponse.model_validate(_sample_report()).model_dump()
    assert set(payload) == {
        "regime_id",
        "compliant",
        "passed",
        "total",
        "checks",
        "generated_at",
        "frameworks",
        "score",
    }
    assert payload["score"] == "7/8"


def test_resolve_regime_dpdp_returns_instance() -> None:
    """'DPDP-2023' resolves to a DPDPRegime instance (AC3)."""
    regime = resolve_regime("DPDP-2023")
    assert isinstance(regime, DPDPRegime)
    assert isinstance(regime, Regime)
    assert regime.regime_id == "DPDP-2023"


def test_resolve_regime_unknown_raises() -> None:
    """An unregistered id raises UnknownRegimeError naming known regimes (AC3)."""
    with pytest.raises(UnknownRegimeError, match="DPDP-2023"):
        resolve_regime("GDPR-2018")


@pytest.mark.parametrize(
    "model",
    [
        DetectRequest,
        DetectResponse,
        AnonymizeRequest,
        AnonymizeResponse,
        ValidateRequest,
        ValidateResponse,
        HealthResponse,
        ErrorResponse,
    ],
)
def test_endpoint_models_build_json_schema(model: type[BaseModel]) -> None:
    """Every endpoint model generates a JSON schema.

    A boundary model whose annotations pydantic cannot turn into a schema (e.g.
    the implicit-recursive ``JsonValue`` alias that failed during Build) would
    blow up here at import/OpenAPI time rather than at first request — and these
    are the wire surface the routers (Step 5) and ``/openapi.json`` depend on.
    """
    schema = model.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
