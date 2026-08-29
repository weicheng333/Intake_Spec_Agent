from copy import deepcopy

import pytest
from pydantic import ValidationError

from intake_spec_agent.contracts import AgentMessage, HandoffEnvelope, IntakeSpecRoleOutput


def test_intake_to_planner_handoff_is_valid(handoff_payload: dict) -> None:
    handoff = HandoffEnvelope.model_validate(handoff_payload)
    assert handoff.sender == "intake_spec"
    assert handoff.recipient == "planner_orchestrator"


def test_intake_handoff_rejects_wrong_recipient(handoff_payload: dict) -> None:
    payload = deepcopy(handoff_payload)
    payload["recipient"] = "executor"
    with pytest.raises(ValidationError, match="接收方必须是 planner_orchestrator"):
        HandoffEnvelope.model_validate(payload)


def test_task_spec_ref_must_be_in_input_refs(handoff_payload: dict) -> None:
    payload = deepcopy(handoff_payload)
    payload["input_refs"] = []
    with pytest.raises(ValidationError, match="task_spec_ref 必须出现在 input_refs"):
        HandoffEnvelope.model_validate(payload)


def test_error_message_requires_error_detail(handoff_payload: dict) -> None:
    payload = {key: value for key, value in handoff_payload.items() if key not in {
        "task_spec_ref", "reason_for_delegation", "expected_output_schema", "artifact_refs", "failure_policy"
    }}
    payload["message_type"] = "ERROR"
    payload["status"] = "FAILED"
    with pytest.raises(ValidationError, match="ERROR 消息必须包含 error"):
        AgentMessage.model_validate(payload)


def test_ready_role_output_requires_matching_ready_artifacts(
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
    handoff_payload: dict,
) -> None:
    output = IntakeSpecRoleOutput.model_validate(
        {
            "schema_version": "1.0.0",
            "status": "READY",
            "requirement_record": ready_requirement_payload,
            "task_spec": ready_task_spec_payload,
            "clarification_questions": [],
            "handoff": handoff_payload,
        }
    )
    assert output.status == "READY"


def test_needs_input_requires_questions(ready_requirement_payload: dict) -> None:
    payload = deepcopy(ready_requirement_payload)
    payload["status"] = "CLARIFYING"
    payload["final_confirmation"] = None
    with pytest.raises(ValidationError, match="NEEDS_INPUT 必须包含 clarification_questions"):
        IntakeSpecRoleOutput.model_validate(
            {
                "schema_version": "1.0.0",
                "status": "NEEDS_INPUT",
                "requirement_record": payload,
                "task_spec": None,
                "clarification_questions": [],
                "handoff": None,
            }
        )
