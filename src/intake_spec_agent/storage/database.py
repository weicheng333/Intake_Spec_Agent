"""SQLite 连接、路径与 schema 迁移。"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .errors import StorageError

SCHEMA_VERSION = 1

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirement_records (
    task_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (task_id, revision),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS task_specs (
    task_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    previous_version INTEGER,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (task_id, version),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE RESTRICT,
    FOREIGN KEY (task_id, previous_version) REFERENCES task_specs(task_id, version)
);

CREATE TABLE IF NOT EXISTS tool_receipts (
    receipt_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (operation, task_id, idempotency_key),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_requirement_records_current
    ON requirement_records(task_id, revision DESC);
CREATE INDEX IF NOT EXISTS idx_task_specs_current
    ON task_specs(task_id, version DESC);
"""


def default_data_directory() -> Path:
    configured = os.environ.get("INTAKE_SPEC_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "intake-spec-agent"
    return Path.home() / ".local" / "share" / "intake-spec-agent"


def default_database_path() -> Path:
    return default_data_directory() / "state.sqlite3"


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_database_path()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > SCHEMA_VERSION:
                raise StorageError(
                    "UNSUPPORTED_DATABASE_VERSION",
                    f"数据库版本 {current} 高于当前支持版本 {SCHEMA_VERSION}",
                )
            if current < 1:
                connection.executescript(MIGRATION_1)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
