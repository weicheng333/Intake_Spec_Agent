"""RequirementRecord 契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import (
    ContractModel,
    ItemId,
    NonEmptyText,
    SCHEMA_VERSION,
    ShortText,
    TaskId,
    TimestampedModel,
    ensure_unique_ids,
    normalized_texts,
)


class RequirementStatus(StrEnum):
    DRAFT = "DRAFT"
    CLARIFYING = "CLARIFYING"
    READY = "READY"


class ConstraintCategory(StrEnum):
    TECHNICAL = "technical"
    PLATFORM = "platform"
    COMPATIBILITY = "compatibility"
    PERFORMANCE = "performance"
    SECURITY = "security"
    PRIVACY = "privacy"
    LEGAL = "legal"
    COST = "cost"
    SCHEDULE = "schedule"
    OTHER = "other"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssumptionStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class UserStatedFact(ContractModel):
    id: ItemId
    statement: NonEmptyText
    source: Literal["user"] = "user"
    source_ref: str | None = Field(default=None, max_length=1_024)


class Constraint(ContractModel):
    id: ItemId
    category: ConstraintCategory
    statement: NonEmptyText
    source_fact_ids: list[ItemId] = Field(default_factory=list)


class Preference(ContractModel):
    id: ItemId
    statement: NonEmptyText
    source_fact_ids: list[ItemId] = Field(default_factory=list)


class Assumption(ContractModel):
    id: ItemId
    statement: NonEmptyText
    status: AssumptionStatus = AssumptionStatus.PROPOSED
    impact: NonEmptyText
    basis: NonEmptyText


class UnknownItem(ContractModel):
    id: ItemId
    question: NonEmptyText
    impact: NonEmptyText
    primary_dimension: ShortText
    related_dimensions: list[ShortText] = Field(default_factory=list, max_length=20)


class Unknowns(ContractModel):
    blocking: list[UnknownItem] = Field(default_factory=list)
    non_blocking: list[UnknownItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unknowns(self) -> "Unknowns":
        ensure_unique_ids(self.blocking + self.non_blocking, "unknowns")
        blocking_questions = normalized_texts([item.question for item in self.blocking])
        non_blocking_questions = normalized_texts([item.question for item in self.non_blocking])
        if blocking_questions & non_blocking_questions:
            raise ValueError("同一未知项不能同时标记为 blocking 和 non-blocking")
        return self


class Scope(ContractModel):
    included: list[NonEmptyText] = Field(default_factory=list)
    excluded: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def prevent_scope_conflicts(self) -> "Scope":
        overlap = normalized_texts(self.included) & normalized_texts(self.excluded)
        if overlap:
            raise ValueError("同一范围项不能同时 included 和 excluded")
        return self


class Actor(ContractModel):
    id: ItemId
    name: ShortText
    role: ShortText
    needs: list[NonEmptyText] = Field(default_factory=list)


class DataRequirement(ContractModel):
    id: ItemId
    description: NonEmptyText
    classification: ShortText | None = None
    retention: ShortText | None = None


class PermissionRequirement(ContractModel):
    id: ItemId
    action: NonEmptyText
    actor: ShortText
    approval_required: bool


class ExceptionCase(ContractModel):
    id: ItemId
    scenario: NonEmptyText
    expected_behavior: NonEmptyText


class AcceptanceExpectation(ContractModel):
    id: ItemId
    statement: NonEmptyText
    verification_hint: NonEmptyText


class Risk(ContractModel):
    id: ItemId
    statement: NonEmptyText
    likelihood: RiskLevel
    impact: RiskLevel
    mitigation: NonEmptyText | None = None


class QuestionOption(ContractModel):
    id: ShortText
    label: ShortText
    impact: NonEmptyText


class ClarificationQuestion(ContractModel):
    id: ItemId
    question: NonEmptyText
    primary_dimension: ShortText
    related_dimensions: list[ShortText] = Field(default_factory=list, max_length=20)
    analysis: NonEmptyText
    options: list[QuestionOption] = Field(min_length=2, max_length=3)
    recommended_option_id: ShortText
    recommendation_reason: NonEmptyText

    @model_validator(mode="after")
    def validate_options(self) -> "ClarificationQuestion":
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("问题选项 id 不得重复")
        if self.recommended_option_id not in option_ids:
            raise ValueError("推荐选项必须属于当前问题")
        return self


class FinalConfirmation(ContractModel):
    confirmed_at: datetime
    confirmed_by: ShortText
    reviewed_revision: int = Field(ge=1)
    confirmed_revision: int = Field(ge=2)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_confirmation(self) -> "FinalConfirmation":
        if self.confirmed_at.tzinfo is None or self.confirmed_at.utcoffset() is None:
            raise ValueError("确认时间必须包含时区")
        if self.reviewed_revision >= self.confirmed_revision:
            raise ValueError("reviewed_revision 必须早于 confirmed_revision")
        return self


class RequirementRecord(TimestampedModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    task_id: TaskId
    revision: int = Field(ge=1)
    status: RequirementStatus
    goal: NonEmptyText | None = None
    success_definition: NonEmptyText | None = None
    user_stated_facts: list[UserStatedFact] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: Unknowns = Field(default_factory=Unknowns)
    risks: list[Risk] = Field(default_factory=list)
    scope: Scope = Field(default_factory=Scope)
    actors: list[Actor] = Field(default_factory=list)
    data_requirements: list[DataRequirement] = Field(default_factory=list)
    permissions: list[PermissionRequirement] = Field(default_factory=list)
    exception_cases: list[ExceptionCase] = Field(default_factory=list)
    acceptance_expectations: list[AcceptanceExpectation] = Field(default_factory=list)
    open_questions: list[ClarificationQuestion] = Field(default_factory=list)
    final_confirmation: FinalConfirmation | None = None

    @model_validator(mode="after")
    def validate_record(self) -> "RequirementRecord":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at 不得早于 created_at")

        collections = {
            "user_stated_facts": self.user_stated_facts,
            "constraints": self.constraints,
            "preferences": self.preferences,
            "assumptions": self.assumptions,
            "risks": self.risks,
            "actors": self.actors,
            "data_requirements": self.data_requirements,
            "permissions": self.permissions,
            "exception_cases": self.exception_cases,
            "acceptance_expectations": self.acceptance_expectations,
            "open_questions": self.open_questions,
        }
        for name, items in collections.items():
            ensure_unique_ids(items, name)

        fact_statements = normalized_texts([item.statement for item in self.user_stated_facts])
        assumption_statements = normalized_texts([item.statement for item in self.assumptions])
        if fact_statements & assumption_statements:
            raise ValueError("用户事实不能同时记录为 Agent 假设")

        fact_ids = {item.id for item in self.user_stated_facts}
        for item in [*self.constraints, *self.preferences]:
            missing = set(item.source_fact_ids) - fact_ids
            if missing:
                raise ValueError(f"{item.id} 引用了不存在的用户事实：{sorted(missing)}")

        if self.status == RequirementStatus.READY:
            if self.goal is None or self.success_definition is None:
                raise ValueError("READY RequirementRecord 必须包含目标和成功定义")
            if self.unknowns.blocking or self.open_questions:
                raise ValueError("存在阻塞未知项或待回答问题时不能进入 READY")
            if not self.scope.included:
                raise ValueError("READY RequirementRecord 必须明确 included scope")
            if not self.acceptance_expectations:
                raise ValueError("READY RequirementRecord 必须包含验收期望")
            if self.final_confirmation is None:
                raise ValueError("READY RequirementRecord 必须包含用户最终核验记录")
            if self.final_confirmation.confirmed_revision != self.revision:
                raise ValueError("最终核验记录必须对应当前 revision")
        elif self.final_confirmation is not None:
            raise ValueError("非 READY RequirementRecord 不得包含最终核验记录")
        return self
