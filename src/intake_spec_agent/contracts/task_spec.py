"""TaskSpec 契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import (
    Budget,
    ContractModel,
    ImmutableRef,
    ItemId,
    NonEmptyText,
    RetryLimits,
    SCHEMA_VERSION,
    TaskId,
    ensure_unique_ids,
    normalized_texts,
)
from .requirement_record import Risk, Scope, UnknownItem


class TaskSpecStatus(StrEnum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    READY_FOR_PLANNING = "READY_FOR_PLANNING"
    SUPERSEDED = "SUPERSEDED"


class VerificationMethod(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    INSPECTION = "inspection"


class Deliverable(ContractModel):
    id: ItemId
    description: NonEmptyText
    artifact_type: NonEmptyText
    acceptance_criterion_ids: list[ItemId] = Field(min_length=1)


class AcceptanceCriterion(ContractModel):
    id: ItemId
    statement: NonEmptyText
    observable_outcome: NonEmptyText
    verification_method: VerificationMethod
    critical: bool = False
    evidence_requirement_ids: list[ItemId] = Field(default_factory=list)


class EvidenceRequirement(ContractModel):
    id: ItemId
    description: NonEmptyText
    acceptable_evidence: list[NonEmptyText] = Field(min_length=1)
    acceptance_criterion_ids: list[ItemId] = Field(min_length=1)


class PermissionBoundary(ContractModel):
    granted: list[NonEmptyText] = Field(default_factory=list)
    requires_approval: list[NonEmptyText] = Field(default_factory=list)
    denied: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def prevent_permission_conflicts(self) -> "PermissionBoundary":
        groups = {
            "granted": normalized_texts(self.granted),
            "requires_approval": normalized_texts(self.requires_approval),
            "denied": normalized_texts(self.denied),
        }
        if groups["granted"] & groups["requires_approval"]:
            raise ValueError("权限不能同时 granted 和 requires_approval")
        if groups["granted"] & groups["denied"]:
            raise ValueError("权限不能同时 granted 和 denied")
        if groups["requires_approval"] & groups["denied"]:
            raise ValueError("权限不能同时 requires_approval 和 denied")
        return self


class TaskSpec(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    task_id: TaskId
    version: int = Field(ge=1)
    status: TaskSpecStatus
    objective: NonEmptyText
    scope: Scope
    deliverables: list[Deliverable] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    constraints: list[NonEmptyText] = Field(default_factory=list)
    allowed_actions: list[NonEmptyText] = Field(default_factory=list)
    prohibited_actions: list[NonEmptyText] = Field(default_factory=list)
    permissions: PermissionBoundary = Field(default_factory=PermissionBoundary)
    assumptions: list[NonEmptyText] = Field(default_factory=list)
    blocking_unknowns: list[UnknownItem] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    deadline: datetime | None = None
    retry_limits: RetryLimits = Field(default_factory=RetryLimits)
    handoff_target: Literal["planner_orchestrator"] = "planner_orchestrator"
    requirement_record_ref: ImmutableRef
    previous_version_ref: ImmutableRef | None = None
    created_at: datetime

    @field_validator("deadline", "created_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_spec(self) -> "TaskSpec":
        ensure_unique_ids(self.deliverables, "deliverables")
        ensure_unique_ids(self.acceptance_criteria, "acceptance_criteria")
        ensure_unique_ids(self.evidence_requirements, "evidence_requirements")
        ensure_unique_ids(self.blocking_unknowns, "blocking_unknowns")
        ensure_unique_ids(self.risks, "risks")

        allowed = normalized_texts(self.allowed_actions)
        prohibited = normalized_texts(self.prohibited_actions)
        if allowed & prohibited:
            raise ValueError("同一动作不能同时 allowed 和 prohibited")

        criterion_ids = {item.id for item in self.acceptance_criteria}
        evidence_ids = {item.id for item in self.evidence_requirements}
        for deliverable in self.deliverables:
            missing = set(deliverable.acceptance_criterion_ids) - criterion_ids
            if missing:
                raise ValueError(f"{deliverable.id} 引用了不存在的验收标准：{sorted(missing)}")
        for criterion in self.acceptance_criteria:
            missing = set(criterion.evidence_requirement_ids) - evidence_ids
            if missing:
                raise ValueError(f"{criterion.id} 引用了不存在的证据要求：{sorted(missing)}")
            if criterion.critical and not criterion.evidence_requirement_ids:
                raise ValueError(f"关键验收标准 {criterion.id} 必须关联证据要求")
        for evidence in self.evidence_requirements:
            missing = set(evidence.acceptance_criterion_ids) - criterion_ids
            if missing:
                raise ValueError(f"{evidence.id} 引用了不存在的验收标准：{sorted(missing)}")

        if self.status == TaskSpecStatus.READY_FOR_PLANNING:
            if self.blocking_unknowns:
                raise ValueError("存在 blocking unknown 时不能进入 READY_FOR_PLANNING")
            if not self.scope.included or not self.deliverables or not self.acceptance_criteria:
                raise ValueError("READY_FOR_PLANNING 必须包含范围、交付物和验收标准")
        if self.status == TaskSpecStatus.BLOCKED and not self.blocking_unknowns:
            raise ValueError("BLOCKED TaskSpec 必须包含 blocking unknown")
        if self.version == 1 and self.previous_version_ref is not None:
            raise ValueError("TaskSpec version 1 不得包含 previous_version_ref")
        if self.version > 1 and self.previous_version_ref is None:
            raise ValueError("TaskSpec 后续版本必须包含 previous_version_ref")
        return self
