import sqlite3
from pathlib import Path

import pytest

from intake_spec_agent.storage import Database, StorageError


def test_database_initialization_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.sqlite3")
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"tasks", "requirement_records", "task_specs", "tool_receipts"} <= tables


def test_newer_database_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 999")
    connection.close()

    with pytest.raises(StorageError, match="高于当前支持版本") as error:
        Database(path).initialize()
    assert error.value.code == "UNSUPPORTED_DATABASE_VERSION"
