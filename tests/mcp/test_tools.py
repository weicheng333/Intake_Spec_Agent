from copy import deepcopy
from pathlib import Path

import pytest

from intake_spec_agent.mcp_server import IntakeSpecTools
from intake_spec_agent.storage import Database, TaskStateRepository


@pytest.fixture
def tools(tmp_path: Path) -> IntakeSpecTools:
    return IntakeSpecTools(TaskStateRepository(Database(tmp_path / "state.sqlite3")))


def _draft_payload(ready_requirement_payload: dict) -> dict:
    requirement = deepcopy(ready_requirement_payload)
    requirement["revision"] = 1
    requirement["status"] = "CLARIFYING"
    requirement["final_confirmation"] = None
    return {"requirement_record": requirement, "task_spec": None}


def _ready_payload(ready_requirement_payload: dict, ready_task_spec_payload: dict) -> dict:
    return {
        "requirement_record": deepcopy(ready_requirement_payload),
        "task_spec": deepcopy(ready_task_spec_payload),
    }


def test_validate_requirement_record_returns_structured_evidence(
    tools: IntakeSpecTools, ready_requirement_payload: dict
) -> None:
    response = tools.validate_requirement_record(ready_requirement_payload)
    assert response.status == "SUCCESS"
    assert response.evidence_ref.startswith("evidence://requirement-validation/sha256/")
    assert response.result == {
        "valid": True,
        "task_id": "TASK-DEMO-001",
        "revision": 2,
        "record_status": "READY",
    }


def test_invalid_task_spec_returns_safe_issues(
    tools: IntakeSpecTools, ready_task_spec_payload: dict
) -> None:
    payload = deepcopy(ready_task_spec_payload)
    payload["deadline"] = "invented"
    response = tools.validate_task_spec(payload)
    assert response.status == "ERROR"
    assert response.error_code == "TASK_SPEC_INVALID"
    assert response.retryable is False
    assert response.issues
    assert all("input" not in issue for issue in response.issues)


def test_policy_allowlist_denies_unknown_reference(tools: IntakeSpecTools) -> None:
    response = tools.read_policy("policy://secret/all")
    assert response.status == "ERROR"
    assert response.error_code == "POLICY_NOT_ALLOWED"


def test_store_and_read_context(
    tools: IntakeSpecTools,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    tools.store_task_spec(
        "TASK-DEMO-001",
        _draft_payload(ready_requirement_payload),
        "mcp-draft-one",
        expected_requirement_revision=0,
        expected_task_spec_version=0,
    )
    payload = _ready_payload(ready_requirement_payload, ready_task_spec_payload)
    stored = tools.store_task_spec(
        "TASK-DEMO-001",
        payload,
        "mcp-store-one",
        expected_requirement_revision=1,
        expected_task_spec_version=0,
    )
    replayed = tools.store_task_spec(
        "TASK-DEMO-001",
        payload,
        "mcp-store-one",
        expected_requirement_revision=1,
        expected_task_spec_version=0,
    )
    context = tools.read_task_context("TASK-DEMO-001")

    assert stored.status == "SUCCESS"
    assert replayed.receipt_ref == stored.receipt_ref
    assert replayed.result is not None and replayed.result["replayed"] is True
    assert context.status == "SUCCESS"
    assert context.result is not None
    assert context.result["task_spec"]["version"] == 1


def test_store_rejects_task_id_mismatch(
    tools: IntakeSpecTools,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    response = tools.store_task_spec(
        "TASK-OTHER-001",
        _ready_payload(ready_requirement_payload, ready_task_spec_payload),
        "wrong-task",
        0,
        0,
    )
    assert response.status == "ERROR"
    assert response.error_code == "TASK_ID_MISMATCH"


def test_read_context_validates_task_id(tools: IntakeSpecTools) -> None:
    response = tools.read_task_context("../secret")
    assert response.status == "ERROR"
    assert response.error_code == "INVALID_TASK_ID"
