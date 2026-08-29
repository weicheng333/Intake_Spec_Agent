"""MCP 工具的确定性业务实现。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from intake_spec_agent.contracts import RequirementRecord, TaskSpec
from intake_spec_agent.contracts.common import TaskId
from intake_spec_agent.storage import StorageError, TaskStateRepository


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCESS", "ERROR"]
    error_code: str | None = None
    retryable: bool = False
    receipt_ref: str | None = None
    evidence_ref: str | None = None
    result: dict[str, Any] | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def prevent_fake_success(self) -> "ToolResponse":
        if self.status == "SUCCESS" and self.error_code is not None:
            raise ValueError("SUCCESS 响应不得包含 error_code")
        if self.status == "ERROR" and self.error_code is None:
            raise ValueError("ERROR 响应必须包含 error_code")
        return self


DEFAULT_POLICIES = {
    "policy://intake-spec/default": {
        "name": "Intake & Spec 默认边界",
        "rules": [
            "只澄清需求并生成任务规格，不执行产品业务动作。",
            "不得把推断升级为用户要求。",
            "只有阻塞未知项才向用户提问。",
            "不得虚构预算、截止日期、权限、证据或工具结果。",
            "下一步属于其他 Agent 时输出 typed handoff。",
        ],
    },
    "policy://intake-spec/permissions": {
        "name": "Intake & Spec 权限边界",
        "rules": [
            "允许读取当前任务上下文和公开策略。",
            "允许校验并保存本 Agent 的任务状态。",
            "禁止 shell、Git 写入、邮件、支付、删除和业务数据库写入。",
            "权限不足时请求审批，禁止自动提权或重复重试。",
        ],
    },
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _evidence_ref(kind: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"evidence://{kind}/sha256/{digest}"


def _validation_issues(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "path": [str(segment) for segment in issue["loc"]],
            "message": issue["msg"],
            "type": issue["type"],
        }
        for issue in error.errors(include_input=False, include_url=False)
    ]


class IntakeSpecTools:
    def __init__(
        self,
        repository: TaskStateRepository,
        *,
        policies: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.repository = repository
        self.policies = policies or DEFAULT_POLICIES

    def read_task_context(
        self,
        task_id: str,
        requirement_revision: int | None = None,
        task_spec_version: int | None = None,
    ) -> ToolResponse:
        try:
            TypeAdapter(TaskId).validate_python(task_id)
        except ValidationError as error:
            return ToolResponse(
                status="ERROR",
                error_code="INVALID_TASK_ID",
                retryable=False,
                issues=_validation_issues(error),
            )
        try:
            state = self.repository.get_state(
                task_id,
                requirement_revision=requirement_revision,
                task_spec_version=task_spec_version,
            )
        except StorageError as error:
            return ToolResponse(
                status="ERROR",
                error_code=error.code,
                retryable=error.retryable,
                result={"message": error.message, "details": error.details},
            )
        result = {
            "requirement_record": state.requirement_record.model_dump(mode="json"),
            "task_spec": None if state.task_spec is None else state.task_spec.model_dump(mode="json"),
        }
        return ToolResponse(
            status="SUCCESS",
            evidence_ref=_evidence_ref("task-context", result),
            result=result,
        )

    def read_policy(self, policy_ref: str) -> ToolResponse:
        policy = self.policies.get(policy_ref)
        if policy is None:
            return ToolResponse(
                status="ERROR",
                error_code="POLICY_NOT_ALLOWED",
                retryable=False,
                result={"message": "该 policy_ref 不在公开策略 allowlist 中"},
            )
        return ToolResponse(
            status="SUCCESS",
            evidence_ref=_evidence_ref("policy", policy),
            result={"policy_ref": policy_ref, "policy": policy},
        )

    def validate_requirement_record(self, payload: dict[str, Any]) -> ToolResponse:
        try:
            record = RequirementRecord.model_validate(payload)
        except ValidationError as error:
            return ToolResponse(
                status="ERROR",
                error_code="REQUIREMENT_RECORD_INVALID",
                retryable=False,
                issues=_validation_issues(error),
            )
        summary = {
            "valid": True,
            "task_id": record.task_id,
            "revision": record.revision,
            "record_status": record.status,
        }
        return ToolResponse(
            status="SUCCESS",
            evidence_ref=_evidence_ref("requirement-validation", record.model_dump(mode="json")),
            result=summary,
        )

    def validate_task_spec(self, payload: dict[str, Any]) -> ToolResponse:
        try:
            spec = TaskSpec.model_validate(payload)
        except ValidationError as error:
            return ToolResponse(
                status="ERROR",
                error_code="TASK_SPEC_INVALID",
                retryable=False,
                issues=_validation_issues(error),
            )
        summary = {
            "valid": True,
            "task_id": spec.task_id,
            "version": spec.version,
            "task_spec_status": spec.status,
        }
        return ToolResponse(
            status="SUCCESS",
            evidence_ref=_evidence_ref("task-spec-validation", spec.model_dump(mode="json")),
            result=summary,
        )

    def store_task_spec(
        self,
        task_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        expected_requirement_revision: int,
        expected_task_spec_version: int,
    ) -> ToolResponse:
        try:
            requirement_record = RequirementRecord.model_validate(payload.get("requirement_record"))
            raw_task_spec = payload.get("task_spec")
            task_spec = None if raw_task_spec is None else TaskSpec.model_validate(raw_task_spec)
        except ValidationError as error:
            return ToolResponse(
                status="ERROR",
                error_code="STATE_PAYLOAD_INVALID",
                retryable=False,
                issues=_validation_issues(error),
            )
        if requirement_record.task_id != task_id or (
            task_spec is not None and task_spec.task_id != task_id
        ):
            return ToolResponse(
                status="ERROR",
                error_code="TASK_ID_MISMATCH",
                retryable=False,
                result={"message": "工具 task_id 与 payload task_id 不一致"},
            )
        try:
            receipt = self.repository.store_state(
                requirement_record,
                task_spec,
                idempotency_key=idempotency_key,
                expected_requirement_revision=expected_requirement_revision,
                expected_task_spec_version=expected_task_spec_version,
            )
        except StorageError as error:
            return ToolResponse(
                status="ERROR",
                error_code=error.code,
                retryable=error.retryable,
                receipt_ref=error.details.get("receipt_ref"),
                result={"message": error.message, "details": error.details},
            )
        return ToolResponse(
            status="SUCCESS",
            receipt_ref=receipt.receipt_ref,
            result={**receipt.as_dict(), "replayed": receipt.replayed},
        )
