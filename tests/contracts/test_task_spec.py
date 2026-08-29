from copy import deepcopy

import pytest
from pydantic import ValidationError

from intake_spec_agent.contracts import TaskSpec


def test_ready_task_spec_is_valid(ready_task_spec_payload: dict) -> None:
    spec = TaskSpec.model_validate(ready_task_spec_payload)
    assert spec.status == "READY_FOR_PLANNING"
    assert spec.budget.max_cost is None


def test_deliverable_must_reference_existing_criterion(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["deliverables"][0]["acceptance_criterion_ids"] = ["criterion_missing"]
    with pytest.raises(ValidationError, match="引用了不存在的验收标准"):
        TaskSpec.model_validate(payload)


def test_critical_criterion_requires_evidence(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["acceptance_criteria"][0]["evidence_requirement_ids"] = []
    with pytest.raises(ValidationError, match="关键验收标准.*必须关联证据要求"):
        TaskSpec.model_validate(payload)


def test_ready_spec_rejects_blocking_unknown(
    ready_task_spec_payload: dict, blocking_unknown_payload: dict
) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["blocking_unknowns"] = [blocking_unknown_payload]
    with pytest.raises(ValidationError, match="存在 blocking unknown"):
        TaskSpec.model_validate(payload)


def test_blocked_spec_requires_blocking_unknown(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["status"] = "BLOCKED"
    with pytest.raises(ValidationError, match="BLOCKED TaskSpec"):
        TaskSpec.model_validate(payload)


def test_allowed_and_prohibited_actions_cannot_overlap(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["prohibited_actions"].append("读取当前任务上下文")
    with pytest.raises(ValidationError, match="同时 allowed 和 prohibited"):
        TaskSpec.model_validate(payload)


def test_permission_groups_cannot_overlap(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["permissions"]["denied"].append("读取当前任务上下文")
    with pytest.raises(ValidationError, match="同时 granted 和 denied"):
        TaskSpec.model_validate(payload)


def test_later_version_requires_previous_ref(ready_task_spec_payload: dict) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["version"] = 2
    with pytest.raises(ValidationError, match="后续版本必须包含 previous_version_ref"):
        TaskSpec.model_validate(payload)
