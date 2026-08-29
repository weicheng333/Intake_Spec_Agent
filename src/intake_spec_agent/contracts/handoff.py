"""跨 Agent 消息、交接和角色输出契约。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import (
    Budget,
    ContractModel,
    ErrorDetail,
    ImmutableRef,
    NonEmptyText,
    RetryLimits,
    SCHEMA_VERSION,
    TaskId,
    TraceId,
)
from .requirement_record import ClarificationQuestion, RequirementRecord, RequirementStatus
from .task_spec import TaskSpec, TaskSpecStatus


class SenderRole(StrEnum):
    INTAKE_SPEC = "intake_spec"
    PLANNER_ORCHESTRATOR = "planner_orchestrator"
    RESEARCH = "research"
    EXECUTOR = "executor"
    VERIFIER = "verifier"


class RecipientRole(StrEnum):
    INTAKE_SPEC = "intake_spec"
    PLANNER_ORCHESTRATOR = "planner_orchestrator"
    RESEARCH = "research"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    HUMAN = "human"


class MessageType(StrEnum):
    TASK = "TASK"
    RESULT = "RESULT"
    EVIDENCE = "EVIDENCE"
    REVISION_REQUEST = "REVISION_REQUEST"
    APPROVAL_REQUEST = "APPROVAL_REQUEST"
    APPROVAL_RESULT = "APPROVAL_RESULT"
    ERROR = "ERROR"
    STATUS = "STATUS"


class AgentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class AgentMessage(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    trace_id: TraceId
    task_id: TaskId
    parent_task_id: TaskId | None = None
    sender: SenderRole
    recipient: RecipientRole
    message_type: MessageType
    status: AgentStatus
    objective: NonEmptyText
    input_refs: list[ImmutableRef] = Field(default_factory=list)
    constraints: list[NonEmptyText] = Field(default_factory=list)
    permissions: list[NonEmptyText] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    acceptance_criteria: list[NonEmptyText] = Field(default_factory=list)
    evidence_refs: list[ImmutableRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None
    next_action: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_error_state(self) -> "AgentMessage":
        if self.message_type == MessageType.ERROR and self.error is None:
            raise ValueError("ERROR 消息必须包含 error")
        if self.status in {AgentStatus.FAILED, AgentStatus.ESCALATED} and self.error is None:
            raise ValueError("FAILED 或 ESCALATED 状态必须包含 error")
        if self.status == AgentStatus.SUCCEEDED and self.error is not None:
            raise ValueError("SUCCEEDED 状态不得包含 error")
        return self


class FailurePolicy(ContractModel):
    retry_limits: RetryLimits = Field(default_factory=RetryLimits)
    permission_denied_action: Literal["REQUEST_APPROVAL"] = "REQUEST_APPROVAL"
    semantic_failure_action: Literal["REQUEST_REPLAN"] = "REQUEST_REPLAN"
    terminal_failure_action: Literal["ESCALATE_TO_HUMAN"] = "ESCALATE_TO_HUMAN"


class HandoffEnvelope(AgentMessage):
    task_spec_ref: ImmutableRef
    reason_for_delegation: NonEmptyText
    expected_output_schema: ImmutableRef
    artifact_refs: list[ImmutableRef] = Field(default_factory=list)
    failure_policy: FailurePolicy = Field(default_factory=FailurePolicy)

    @model_validator(mode="after")
    def validate_handoff(self) -> "HandoffEnvelope":
        if self.sender == SenderRole.INTAKE_SPEC:
            if self.recipient != RecipientRole.PLANNER_ORCHESTRATOR:
                raise ValueError("intake_spec 的任务交接接收方必须是 planner_orchestrator")
            if self.message_type != MessageType.TASK:
                raise ValueError("intake_spec 交给 Planner 的消息类型必须是 TASK")
            if self.status != AgentStatus.PENDING:
                raise ValueError("intake_spec 交给 Planner 的初始状态必须是 PENDING")
        if self.task_spec_ref not in self.input_refs:
            raise ValueError("task_spec_ref 必须出现在 input_refs 中")
        return self


class IntakeSpecOutputStatus(StrEnum):
    NEEDS_INPUT = "NEEDS_INPUT"
    READY = "READY"


class IntakeSpecRoleOutput(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    status: IntakeSpecOutputStatus
    requirement_record: RequirementRecord
    task_spec: TaskSpec | None = None
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    handoff: HandoffEnvelope | None = None

    @model_validator(mode="after")
    def validate_role_output(self) -> "IntakeSpecRoleOutput":
        if self.requirement_record.task_id != (self.task_spec.task_id if self.task_spec else self.requirement_record.task_id):
            raise ValueError("RequirementRecord 与 TaskSpec 的 task_id 必须一致")
        if self.handoff is not None and self.handoff.task_id != self.requirement_record.task_id:
            raise ValueError("handoff 与 RequirementRecord 的 task_id 必须一致")

        if self.status == IntakeSpecOutputStatus.NEEDS_INPUT:
            if not self.clarification_questions:
                raise ValueError("NEEDS_INPUT 必须包含 clarification_questions")
            if self.handoff is not None:
                raise ValueError("NEEDS_INPUT 不得生成 Planner handoff")
            if self.requirement_record.status == RequirementStatus.READY:
                raise ValueError("NEEDS_INPUT 的 RequirementRecord 不得为 READY")
        else:
            if self.clarification_questions:
                raise ValueError("READY 不得保留 clarification_questions")
            if self.requirement_record.status != RequirementStatus.READY:
                raise ValueError("READY 输出必须包含 READY RequirementRecord")
            if self.task_spec is None or self.task_spec.status != TaskSpecStatus.READY_FOR_PLANNING:
                raise ValueError("READY 输出必须包含 READY_FOR_PLANNING TaskSpec")
            if self.handoff is None:
                raise ValueError("READY 输出必须包含 Planner handoff")
        return self
