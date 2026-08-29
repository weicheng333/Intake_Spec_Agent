from copy import deepcopy
from pathlib import Path

import pytest

from intake_spec_agent.contracts import RequirementRecord, TaskSpec
from intake_spec_agent.mcp_server import IntakeSpecTools
from intake_spec_agent.storage import Database, StorageError, TaskStateRepository


class DeniedRepository:
    calls = 0

    def get_state(self, *args, **kwargs):
        self.calls += 1
        raise StorageError("PERMISSION_DENIED", "权限不足", retryable=False)


def test_permission_denied_is_not_retried() -> None:
    repository = DeniedRepository()
    tools = IntakeSpecTools(repository)  # type: ignore[arg-type]
    response = tools.read_task_context("TASK-DENIED-001")
    assert response.status == "ERROR"
    assert response.error_code == "PERMISSION_DENIED"
    assert response.retryable is False
    assert repository.calls == 1


def test_unexpected_failure_rolls_back_entire_transaction(
    tmp_path: Path, ready_requirement_payload: dict
) -> None:
    draft = deepcopy(ready_requirement_payload)
    draft["revision"] = 1
    draft["status"] = "CLARIFYING"
    draft["final_confirmation"] = None
    repository = TaskStateRepository(
        Database(tmp_path / "state.sqlite3"),
        new_receipt_id=lambda: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )

    with pytest.raises(StorageError) as error:
        repository.store_state(
            RequirementRecord.model_validate(draft),
            None,
            idempotency_key="injected-failure",
            expected_requirement_revision=0,
            expected_task_spec_version=0,
        )
    assert error.value.code == "INTERNAL_STORAGE_ERROR"
    with pytest.raises(StorageError) as missing:
        repository.get_state("TASK-DEMO-001")
    assert missing.value.code == "TASK_NOT_FOUND"


def test_invalid_idempotency_key_fails_before_write(
    tmp_path: Path, ready_requirement_payload: dict
) -> None:
    draft = deepcopy(ready_requirement_payload)
    draft["revision"] = 1
    draft["status"] = "CLARIFYING"
    draft["final_confirmation"] = None
    repository = TaskStateRepository(Database(tmp_path / "state.sqlite3"))
    with pytest.raises(StorageError) as error:
        repository.store_state(
            RequirementRecord.model_validate(draft),
            None,
            idempotency_key="",
            expected_requirement_revision=0,
            expected_task_spec_version=0,
        )
    assert error.value.code == "INVALID_IDEMPOTENCY_KEY"


def test_atomic_initialization_rolls_back_both_versions_on_receipt_failure(
    tmp_path: Path,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    reviewed_requirement = deepcopy(ready_requirement_payload)
    reviewed_requirement["revision"] = 1
    reviewed_requirement["status"] = "CLARIFYING"
    reviewed_requirement["final_confirmation"] = None
    reviewed_spec = deepcopy(ready_task_spec_payload)
    reviewed_spec["status"] = "DRAFT"
    confirmed_spec = deepcopy(ready_task_spec_payload)
    confirmed_spec["version"] = 2
    confirmed_spec["previous_version_ref"] = "evidence://temporary/reviewed"
    repository = TaskStateRepository(
        Database(tmp_path / "state.sqlite3"),
        new_receipt_id=lambda: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )

    with pytest.raises(StorageError) as error:
        repository.initialize_confirmed_state(
            RequirementRecord.model_validate(reviewed_requirement),
            TaskSpec.model_validate(reviewed_spec),
            RequirementRecord.model_validate(ready_requirement_payload),
            TaskSpec.model_validate(confirmed_spec),
            idempotency_key="atomic-injected-failure",
        )
    assert error.value.code == "INTERNAL_STORAGE_ERROR"
    with pytest.raises(StorageError) as missing:
        repository.get_state("TASK-DEMO-001")
    assert missing.value.code == "TASK_NOT_FOUND"
