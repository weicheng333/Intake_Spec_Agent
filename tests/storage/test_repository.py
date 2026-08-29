from copy import deepcopy
from pathlib import Path

import pytest

from intake_spec_agent.contracts import RequirementRecord, TaskSpec
from intake_spec_agent.storage import Database, StorageError, TaskStateRepository


@pytest.fixture
def repository(tmp_path: Path) -> TaskStateRepository:
    counter = iter(["receipt-one", "receipt-two", "receipt-three", "receipt-four"])
    return TaskStateRepository(
        Database(tmp_path / "state.sqlite3"),
        now=lambda: "2026-08-29T02:00:00+00:00",
        new_receipt_id=lambda: next(counter),
    )


def _draft_and_ready(ready_requirement_payload: dict, ready_task_spec_payload: dict):
    draft = deepcopy(ready_requirement_payload)
    draft["revision"] = 1
    draft["status"] = "CLARIFYING"
    draft["final_confirmation"] = None
    return (
        RequirementRecord.model_validate(draft),
        RequirementRecord.model_validate(ready_requirement_payload),
        TaskSpec.model_validate(ready_task_spec_payload),
    )


def test_store_and_read_state(
    repository: TaskStateRepository,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    draft, requirement, task_spec = _draft_and_ready(
        ready_requirement_payload, ready_task_spec_payload
    )
    repository.store_state(
        draft,
        None,
        idempotency_key="draft-one",
        expected_requirement_revision=0,
        expected_task_spec_version=0,
    )
    receipt = repository.store_state(
        requirement,
        task_spec,
        idempotency_key="create-one",
        expected_requirement_revision=1,
        expected_task_spec_version=0,
    )

    assert receipt.receipt_ref == "receipt://receipt-two"
    assert receipt.replayed is False
    state = repository.get_state("TASK-DEMO-001")
    assert state.requirement_record.revision == 2
    assert state.task_spec is not None and state.task_spec.version == 1


def test_same_idempotency_key_and_payload_replays_receipt(
    repository: TaskStateRepository,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    draft, _, _ = _draft_and_ready(ready_requirement_payload, ready_task_spec_payload)
    arguments = {
        "idempotency_key": "same-key",
        "expected_requirement_revision": 0,
        "expected_task_spec_version": 0,
    }
    first = repository.store_state(draft, None, **arguments)
    second = repository.store_state(draft, None, **arguments)

    assert second.receipt_ref == first.receipt_ref
    assert second.replayed is True


def test_same_idempotency_key_with_different_payload_conflicts(
    repository: TaskStateRepository,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    draft, _, _ = _draft_and_ready(ready_requirement_payload, ready_task_spec_payload)
    repository.store_state(
        draft,
        None,
        idempotency_key="conflict-key",
        expected_requirement_revision=0,
        expected_task_spec_version=0,
    )
    changed = draft.model_copy(update={"goal": "另一个目标"})

    with pytest.raises(StorageError) as error:
        repository.store_state(
            changed,
            None,
            idempotency_key="conflict-key",
            expected_requirement_revision=0,
            expected_task_spec_version=0,
        )
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_revision_conflict_writes_nothing(
    repository: TaskStateRepository,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    draft, _, _ = _draft_and_ready(ready_requirement_payload, ready_task_spec_payload)
    with pytest.raises(StorageError) as error:
        repository.store_state(
            draft,
            None,
            idempotency_key="bad-revision",
            expected_requirement_revision=3,
            expected_task_spec_version=0,
        )
    assert error.value.code == "REVISION_CONFLICT"
    with pytest.raises(StorageError) as missing:
        repository.get_state("TASK-DEMO-001")
    assert missing.value.code == "TASK_NOT_FOUND"


def test_append_and_restore_create_new_versions(
    repository: TaskStateRepository,
    ready_requirement_payload: dict,
    ready_task_spec_payload: dict,
) -> None:
    draft, requirement, task_spec = _draft_and_ready(
        ready_requirement_payload, ready_task_spec_payload
    )
    repository.store_state(
        draft,
        None,
        idempotency_key="draft-v1",
        expected_requirement_revision=0,
        expected_task_spec_version=0,
    )
    repository.store_state(
        requirement,
        task_spec,
        idempotency_key="v1",
        expected_requirement_revision=1,
        expected_task_spec_version=0,
    )

    requirement_v3 = requirement.model_copy(
        update={
            "revision": 3,
            "final_confirmation": requirement.final_confirmation.model_copy(
                update={"reviewed_revision": 2, "confirmed_revision": 3}
            ),
        }
    )
    task_spec_v2 = task_spec.model_copy(
        update={
            "version": 2,
            "objective": "第二版目标",
            "previous_version_ref": "taskspec://TASK-DEMO-001/v1",
        }
    )
    repository.store_state(
        requirement_v3,
        task_spec_v2,
        idempotency_key="v2",
        expected_requirement_revision=2,
        expected_task_spec_version=1,
    )
    repository.restore_task_spec(
        "TASK-DEMO-001",
        1,
        idempotency_key="restore-v1",
        expected_task_spec_version=2,
    )

    latest = repository.get_state("TASK-DEMO-001")
    old = repository.get_state("TASK-DEMO-001", task_spec_version=2)
    assert latest.requirement_record.revision == 4
    assert latest.requirement_record.status == "CLARIFYING"
    assert latest.requirement_record.final_confirmation is None
    assert latest.task_spec is not None and latest.task_spec.version == 3
    assert latest.task_spec.status == "DRAFT"
    assert latest.task_spec.objective == task_spec.objective
    assert latest.task_spec.previous_version_ref == "taskspec://TASK-DEMO-001/v2"
    assert old.task_spec is not None and old.task_spec.objective == "第二版目标"
