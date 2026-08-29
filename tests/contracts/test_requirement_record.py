from copy import deepcopy

import pytest
from pydantic import ValidationError

from intake_spec_agent.contracts import RequirementRecord


def test_ready_requirement_record_is_valid(ready_requirement_payload: dict) -> None:
    record = RequirementRecord.model_validate(ready_requirement_payload)
    assert record.status == "READY"
    assert record.task_id == "TASK-DEMO-001"


def test_unknown_fields_are_rejected(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["invented_deadline"] = "tomorrow"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RequirementRecord.model_validate(payload)


def test_ready_record_rejects_blocking_unknown(
    ready_requirement_payload: dict, blocking_unknown_payload: dict
) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["unknowns"]["blocking"] = [blocking_unknown_payload]
    with pytest.raises(ValidationError, match="存在阻塞未知项"):
        RequirementRecord.model_validate(payload)


def test_ready_record_requires_matching_final_confirmation(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["final_confirmation"]["confirmed_revision"] = 3
    with pytest.raises(ValidationError, match="最终核验记录必须对应当前 revision"):
        RequirementRecord.model_validate(payload)


def test_clarifying_record_cannot_claim_final_confirmation(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["status"] = "CLARIFYING"
    with pytest.raises(ValidationError, match="非 READY.*不得包含最终核验记录"):
        RequirementRecord.model_validate(payload)


def test_fact_cannot_also_be_assumption(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["assumptions"] = [
        {
            "id": "assumption_python",
            "statement": "整套 Agent 系统优先使用 Python。",
            "status": "proposed",
            "impact": "会影响技术栈。",
            "basis": "Agent 推测。",
        }
    ]
    with pytest.raises(ValidationError, match="用户事实不能同时记录为 Agent 假设"):
        RequirementRecord.model_validate(payload)


def test_scope_conflict_is_rejected(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["scope"]["excluded"].append("intake & spec agent")
    with pytest.raises(ValidationError, match="同时 included 和 excluded"):
        RequirementRecord.model_validate(payload)


def test_constraint_must_reference_existing_fact(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["constraints"][0]["source_fact_ids"] = ["fact_missing"]
    with pytest.raises(ValidationError, match="引用了不存在的用户事实"):
        RequirementRecord.model_validate(payload)


def test_timestamps_require_timezone(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["created_at"] = "2026-08-29T08:00:00"
    with pytest.raises(ValidationError, match="时间必须包含时区"):
        RequirementRecord.model_validate(payload)


def test_question_recommendation_must_reference_option(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["status"] = "CLARIFYING"
    payload["final_confirmation"] = None
    payload["open_questions"] = [
        {
            "id": "question_scope",
            "question": "是否实现 Planner？",
            "primary_dimension": "范围",
            "related_dimensions": ["验收标准"],
            "analysis": "该决定会改变实现范围。",
            "options": [
                {"id": "A", "label": "不实现", "impact": "保持单 Agent 范围。"},
                {"id": "B", "label": "实现", "impact": "扩大工作量。"},
            ],
            "recommended_option_id": "C",
            "recommendation_reason": "先稳定规格出口。",
        }
    ]
    with pytest.raises(ValidationError, match="推荐选项必须属于当前问题"):
        RequirementRecord.model_validate(payload)
