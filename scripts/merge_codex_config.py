#!/usr/bin/env python3
"""安全合并或移除 Intake & Spec Agent 的 Codex MCP 配置。"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

BEGIN_MARKER = "# BEGIN intake-spec-agent managed MCP"
END_MARKER = "# END intake-spec-agent managed MCP"
TABLE_NAME = "intake_spec_mcp"


class ConfigMergeError(RuntimeError):
    pass


def _toml_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _parse(content: str, path: Path) -> dict:
    try:
        return tomllib.loads(content) if content.strip() else {}
    except tomllib.TOMLDecodeError as error:
        raise ConfigMergeError(f"无法安全解析 TOML：{path}：{error}") from error


def _managed_span(content: str) -> tuple[int, int] | None:
    begin_count = content.count(BEGIN_MARKER)
    end_count = content.count(END_MARKER)
    if begin_count != end_count or begin_count > 1:
        raise ConfigMergeError("Intake & Spec Agent 配置所有权标记不完整或重复")
    if begin_count == 0:
        return None
    begin = content.index(BEGIN_MARKER)
    end = content.index(END_MARKER, begin) + len(END_MARKER)
    while end < len(content) and content[end] in "\r\n":
        end += 1
    return begin, end


def _render_block(runtime_python: Path, runtime_directory: Path, data_directory: Path) -> str:
    return "\n".join(
        [
            BEGIN_MARKER,
            f"[mcp_servers.{TABLE_NAME}]",
            f"command = {_toml_string(runtime_python)}",
            'args = ["-m", "intake_spec_agent.mcp_server.server"]',
            f"cwd = {_toml_string(runtime_directory)}",
            (
                "env = { INTAKE_SPEC_DATA_DIR = "
                f"{_toml_string(data_directory)} }}"
            ),
            "enabled = true",
            "startup_timeout_sec = 20",
            "tool_timeout_sec = 45",
            'default_tools_approval_mode = "writes"',
            END_MARKER,
            "",
        ]
    )


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = path.with_name(f"{path.name}.bak.intake-spec-agent.{timestamp}")
    backup.write_bytes(path.read_bytes())
    return backup


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install_config(
    path: Path,
    *,
    runtime_python: Path,
    runtime_directory: Path,
    data_directory: Path,
) -> Path | None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    parsed = _parse(original, path)
    span = _managed_span(original)
    configured_servers = parsed.get("mcp_servers", {})
    if span is None and TABLE_NAME in configured_servers:
        raise ConfigMergeError(
            f"{path} 已有非本安装器管理的 mcp_servers.{TABLE_NAME}，拒绝覆盖"
        )

    block = _render_block(runtime_python, runtime_directory, data_directory)
    if span is None:
        prefix = original
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        updated = prefix + block
    else:
        updated = original[: span[0]] + block + original[span[1] :]

    _parse(updated, path)
    if updated == original:
        return None
    backup = _backup(path)
    _atomic_write(path, updated)
    return backup


def uninstall_config(path: Path) -> Path | None:
    if not path.exists():
        return None
    original = path.read_text(encoding="utf-8")
    _parse(original, path)
    span = _managed_span(original)
    if span is None:
        return None
    updated = original[: span[0]] + original[span[1] :]
    updated = updated.rstrip() + ("\n" if updated.strip() else "")
    _parse(updated, path)
    backup = _backup(path)
    _atomic_write(path, updated)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    install = subparsers.add_parser("install")
    install.add_argument("--config", type=Path, required=True)
    install.add_argument("--runtime-python", type=Path, required=True)
    install.add_argument("--runtime-directory", type=Path, required=True)
    install.add_argument("--data-directory", type=Path, required=True)
    uninstall = subparsers.add_parser("uninstall")
    uninstall.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        if arguments.action == "install":
            backup = install_config(
                arguments.config,
                runtime_python=arguments.runtime_python,
                runtime_directory=arguments.runtime_directory,
                data_directory=arguments.data_directory,
            )
        else:
            backup = uninstall_config(arguments.config)
    except ConfigMergeError as error:
        parser.error(str(error))
    print("unchanged" if backup is None else f"backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
