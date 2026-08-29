"""RequirementRecord、TaskSpec 与工具回执仓库。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from intake_spec_agent.contracts import RequirementRecord, TaskSpec

from .database import Database
from .errors import StorageError


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ToolReceipt:
    receipt_ref: str
    operation: str
    task_id: str
    requirement_record_ref: str
    task_spec_ref: str | None
    replayed: bool
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_ref": self.receipt_ref,
            "operation": self.operation,
            "task_id": self.task_id,
            "requirement_record_ref": self.requirement_record_ref,
            "task_spec_ref": self.task_spec_ref,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class StoredState:
    requirement_record: RequirementRecord
    task_spec: TaskSpec | None


class TaskStateRepository:
    def __init__(
        self,
        database: Database,
        *,
        now: Callable[[], str] = _utc_now,
        new_receipt_id: Callable[[], str] | None = None,
    ) -> None:
        self.database = database
        self.now = now
        self.new_receipt_id = new_receipt_id or (lambda: f"receipt-{uuid4()}")
        self.database.initialize()

    @staticmethod
    def _current_version(connection: sqlite3.Connection, table: str, column: str, task_id: str) -> int:
        row = connection.execute(
            f"SELECT MAX({column}) AS current_version FROM {table} WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return int(row["current_version"] or 0)

    @staticmethod
    def _existing_receipt(
        connection: sqlite3.Connection,
        operation: str,
        task_id: str,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT receipt_id, request_hash, response_json, created_at
            FROM tool_receipts
            WHERE operation = ? AND task_id = ? AND idempotency_key = ?
            """,
            (operation, task_id, idempotency_key),
        ).fetchone()

    def store_state(
        self,
        requirement_record: RequirementRecord,
        task_spec: TaskSpec | None,
        *,
        idempotency_key: str,
        expected_requirement_revision: int,
        expected_task_spec_version: int,
    ) -> ToolReceipt:
        requirement_record = RequirementRecord.model_validate(
            requirement_record.model_dump(mode="json")
        )
        task_spec = (
            None
            if task_spec is None
            else TaskSpec.model_validate(task_spec.model_dump(mode="json"))
        )
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise StorageError("INVALID_IDEMPOTENCY_KEY", "idempotency key 长度必须为 1–200")
        if task_spec is not None and task_spec.task_id != requirement_record.task_id:
            raise StorageError("TASK_ID_MISMATCH", "RequirementRecord 与 TaskSpec 的 task_id 不一致")

        request = {
            "requirement_record": requirement_record.model_dump(mode="json"),
            "task_spec": None if task_spec is None else task_spec.model_dump(mode="json"),
            "expected_requirement_revision": expected_requirement_revision,
            "expected_task_spec_version": expected_task_spec_version,
        }
        request_hash = _sha256(_canonical_json(request))
        operation = "store_task_spec"

        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._existing_receipt(
                connection, operation, requirement_record.task_id, idempotency_key
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise StorageError(
                        "IDEMPOTENCY_CONFLICT",
                        "相同 idempotency key 已用于不同 payload",
                        details={"receipt_ref": f"receipt://{existing['receipt_id']}"},
                    )
                response = json.loads(existing["response_json"])
                connection.rollback()
                return ToolReceipt(**response, replayed=True)

            current_requirement = self._current_version(
                connection, "requirement_records", "revision", requirement_record.task_id
            )
            current_task_spec = self._current_version(
                connection, "task_specs", "version", requirement_record.task_id
            )
            if current_requirement != expected_requirement_revision:
                raise StorageError(
                    "REVISION_CONFLICT",
                    "RequirementRecord 当前 revision 与 expected revision 不一致",
                    details={"expected": expected_requirement_revision, "actual": current_requirement},
                )
            if current_task_spec != expected_task_spec_version:
                raise StorageError(
                    "VERSION_CONFLICT",
                    "TaskSpec 当前 version 与 expected version 不一致",
                    details={"expected": expected_task_spec_version, "actual": current_task_spec},
                )
            if requirement_record.revision != current_requirement + 1:
                raise StorageError(
                    "INVALID_NEXT_REVISION",
                    "RequirementRecord 必须追加连续 revision",
                    details={"required": current_requirement + 1},
                )
            if task_spec is not None:
                if task_spec.version != current_task_spec + 1:
                    raise StorageError(
                        "INVALID_NEXT_VERSION",
                        "TaskSpec 必须追加连续 version",
                        details={"required": current_task_spec + 1},
                    )
                expected_previous = (
                    None
                    if current_task_spec == 0
                    else f"taskspec://{task_spec.task_id}/v{current_task_spec}"
                )
                if task_spec.previous_version_ref != expected_previous:
                    raise StorageError(
                        "INVALID_PREVIOUS_VERSION_REF",
                        "TaskSpec previous_version_ref 必须指向当前版本",
                        details={"required": expected_previous},
                    )

            timestamp = self.now()
            connection.execute(
                """
                INSERT INTO tasks(task_id, created_at, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (requirement_record.task_id, timestamp, timestamp),
            )
            requirement_json = _canonical_json(requirement_record.model_dump(mode="json"))
            connection.execute(
                """
                INSERT INTO requirement_records(task_id, revision, payload_json, payload_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    requirement_record.task_id,
                    requirement_record.revision,
                    requirement_json,
                    _sha256(requirement_json),
                    timestamp,
                ),
            )

            task_spec_ref: str | None = None
            if task_spec is not None:
                task_spec_json = _canonical_json(task_spec.model_dump(mode="json"))
                connection.execute(
                    """
                    INSERT INTO task_specs(
                        task_id, version, previous_version, payload_json, payload_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_spec.task_id,
                        task_spec.version,
                        current_task_spec or None,
                        task_spec_json,
                        _sha256(task_spec_json),
                        timestamp,
                    ),
                )
                task_spec_ref = f"taskspec://{task_spec.task_id}/v{task_spec.version}"

            receipt_id = self.new_receipt_id()
            response = {
                "receipt_ref": f"receipt://{receipt_id}",
                "operation": operation,
                "task_id": requirement_record.task_id,
                "requirement_record_ref": (
                    f"requirement://{requirement_record.task_id}/v{requirement_record.revision}"
                ),
                "task_spec_ref": task_spec_ref,
                "created_at": timestamp,
            }
            connection.execute(
                """
                INSERT INTO tool_receipts(
                    receipt_id, operation, task_id, idempotency_key,
                    request_hash, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    operation,
                    requirement_record.task_id,
                    idempotency_key,
                    request_hash,
                    _canonical_json(response),
                    timestamp,
                ),
            )
            connection.commit()
            return ToolReceipt(**response, replayed=False)
        except StorageError:
            connection.rollback()
            raise
        except sqlite3.OperationalError as error:
            connection.rollback()
            raise StorageError("DATABASE_BUSY", str(error), retryable=True) from error
        except sqlite3.DatabaseError as error:
            connection.rollback()
            raise StorageError("DATABASE_ERROR", str(error), retryable=False) from error
        except Exception as error:
            connection.rollback()
            raise StorageError(
                "INTERNAL_STORAGE_ERROR", "存储事务未完成", retryable=False
            ) from error
        finally:
            connection.close()

    def get_state(
        self,
        task_id: str,
        *,
        requirement_revision: int | None = None,
        task_spec_version: int | None = None,
    ) -> StoredState:
        with self.database.connect() as connection:
            requirement_row = connection.execute(
                """
                SELECT payload_json FROM requirement_records
                WHERE task_id = ? AND revision = COALESCE(
                    ?, (SELECT MAX(revision) FROM requirement_records WHERE task_id = ?)
                )
                """,
                (task_id, requirement_revision, task_id),
            ).fetchone()
            if requirement_row is None:
                raise StorageError("TASK_NOT_FOUND", f"未找到任务 {task_id}")
            task_spec_row = connection.execute(
                """
                SELECT payload_json FROM task_specs
                WHERE task_id = ? AND version = COALESCE(
                    ?, (SELECT MAX(version) FROM task_specs WHERE task_id = ?)
                )
                """,
                (task_id, task_spec_version, task_id),
            ).fetchone()
        return StoredState(
            requirement_record=RequirementRecord.model_validate_json(requirement_row["payload_json"]),
            task_spec=(
                None
                if task_spec_row is None
                else TaskSpec.model_validate_json(task_spec_row["payload_json"])
            ),
        )

    def restore_task_spec(
        self,
        task_id: str,
        source_version: int,
        *,
        idempotency_key: str,
        expected_task_spec_version: int,
    ) -> ToolReceipt:
        current = self.get_state(task_id)
        source = self.get_state(task_id, task_spec_version=source_version)
        if current.task_spec is None or source.task_spec is None:
            raise StorageError("TASK_SPEC_NOT_FOUND", "任务没有可回退的 TaskSpec")
        next_spec = source.task_spec.model_copy(
            update={
                "version": expected_task_spec_version + 1,
                "status": "DRAFT",
                "previous_version_ref": f"taskspec://{task_id}/v{expected_task_spec_version}",
                "created_at": datetime.fromisoformat(self.now()),
            }
        )
        next_requirement = current.requirement_record.model_copy(
            update={
                "revision": current.requirement_record.revision + 1,
                "status": "CLARIFYING",
                "final_confirmation": None,
                "updated_at": datetime.fromisoformat(self.now()),
            }
        )
        return self.store_state(
            next_requirement,
            next_spec,
            idempotency_key=idempotency_key,
            expected_requirement_revision=current.requirement_record.revision,
            expected_task_spec_version=expected_task_spec_version,
        )
