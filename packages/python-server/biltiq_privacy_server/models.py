# SPDX-License-Identifier: MIT
"""Pydantic v2 wire models — the JSON ↔ library serialisation boundary (BILTIQ-013).

These models carry **no business logic**; they only translate JSON into the
arguments the library expects and the library's result types back into JSON.
Each element model mirrors one authoritative library type one-to-one, so a drift
between the wire shape and the library record surfaces as a test failure (the
field-name drift guard in ``tests/test_models.py``) rather than a silent
divergence — the "thin-shim watch" the design calls for.

Pydantic v2 API exclusively: ``model_validate`` / ``model_dump`` /
``field_validator``. The deprecated v1 spellings (``parse_obj`` / ``.dict()`` /
``@validator``) are never used (approved-versions.md, Anti-Pattern #9).

Serialisation mechanics:

* The library TypedDicts (``DetectedEntity``, ``AuditRecord``, ``ChainedRow``)
  are plain ``dict`` at runtime, so ``Model.model_validate(d)`` validates them
  directly with no manual field copying.
* The frozen dataclasses (``ComplianceCheck`` / ``ComplianceReport``) validate
  via ``ConfigDict(from_attributes=True)``. ``ComplianceReport.score`` is a
  derived ``@property``, not a stored field; it is carried into the response
  because pydantic reads each declared field by attribute access, which resolves
  the property descriptor even on a ``slots=True`` dataclass.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

# --- Element models (each mirrors one library record type) -------------------


class DetectionModel(BaseModel):
    """Mirrors :class:`biltiq_privacy.DetectedEntity` (TypedDict: six keys)."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    text: str
    start: int
    end: int
    score: float
    source: str


class AuditRecordModel(BaseModel):
    """Mirrors :class:`biltiq_privacy.AuditRecord` (TypedDict: five keys)."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    pseudonym_token: str
    position_start: int
    position_end: int
    confidence: float


class AuditRowModel(BaseModel):
    """Mirrors :class:`biltiq_privacy.ChainedRow` (TypedDict).

    ``payload`` uses pydantic's native ``JsonValue`` (a recursive JSON type)
    rather than ``Any`` so the opaque, caller-owned event mapping stays strictly
    typed (AP #4). The library's own ``JsonValue`` is an *implicit* recursive
    ``TypeAlias`` that pydantic v2 cannot build a schema for, so the wire model
    uses pydantic's equivalent here — the two describe the same value space.
    """

    model_config = ConfigDict(from_attributes=True)

    prev_hash: str
    payload: dict[str, JsonValue]
    hash: str


class ComplianceCheckModel(BaseModel):
    """Mirrors :class:`biltiq_privacy.ComplianceCheck` (frozen dataclass)."""

    model_config = ConfigDict(from_attributes=True)

    check_id: str
    name: str
    description: str
    status: str
    details: str
    section: str
    evidence: tuple[str, ...] = ()


class ComplianceReportModel(BaseModel):
    """Mirrors :class:`biltiq_privacy.ComplianceReport` (frozen dataclass).

    ``score`` is the dataclass's derived ``@property`` (e.g. ``"7/8"``), echoed
    into the response (see module docstring on property carry-through).
    """

    model_config = ConfigDict(from_attributes=True)

    regime_id: str
    compliant: bool
    passed: int
    total: int
    checks: tuple[ComplianceCheckModel, ...]
    generated_at: str
    frameworks: tuple[str, ...]
    score: str


# --- Endpoint request / response models --------------------------------------


class DetectRequest(BaseModel):
    """POST /detect body (AC1)."""

    text: str
    language: str = "en"
    score_threshold: float | None = None  # None -> server/settings default


class DetectResponse(BaseModel):
    """POST /detect response: the detected spans plus their count (AC1)."""

    detections: list[DetectionModel]
    count: int


class AnonymizeRequest(BaseModel):
    """POST /anonymize body (AC2).

    ``generated_at`` and ``prev_hash`` are optional: the server supplies the
    timestamp (it is the system boundary) and the genesis hash when omitted.
    The HMAC key is **never** a body field — it is injected via ``Depends``
    (AC6).
    """

    text: str
    generated_at: str | None = None  # None -> server UTC clock (boundary)
    regime: str | None = None  # None -> skip compliance attestation
    generalise: bool = True
    prev_hash: str | None = None  # None -> GENESIS_PREV_HASH


class AnonymizeResponse(BaseModel):
    """POST /anonymize response — mirrors ``AnonymiseResult`` field-by-field (AC2).

    ``original_text`` is deliberately absent: the library drops it to narrow the
    PII surface, and the wire model follows.
    """

    anonymised_text: str
    detections: list[DetectionModel]
    audit_records: list[AuditRecordModel]
    audit_row: AuditRowModel
    compliance: ComplianceReportModel | None


class ValidateRequest(BaseModel):
    """POST /validate body (AC3). ``regime`` is required; unknown -> 422."""

    original_text: str
    anonymised_text: str
    detections: list[DetectionModel]
    audit_records: list[AuditRecordModel]
    generated_at: str | None = None
    regime: str


class ValidateResponse(ComplianceReportModel):
    """POST /validate response: the full compliance report (AC3)."""


class HealthResponse(BaseModel):
    """GET /healthz response (AC4). ``reason`` is populated only when degraded."""

    status: str
    version: str
    reason: str | None = None


class ErrorResponse(BaseModel):
    """The uniform error envelope every handler emits (AC11)."""

    detail: str
    code: str
