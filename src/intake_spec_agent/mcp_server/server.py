"""本地 STDIO MCP 服务入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from intake_spec_agent.storage import Database, TaskStateRepository

from .tools import IntakeSpecTools, ToolResponse

SERVER_INSTRUCTIONS = """
只提供 Intake & Spec Agent 的当前任务读取、公开策略读取、契约校验和版本化状态保存。
未注册的能力默认拒绝；本服务不提供 shell、Git、邮件、支付、删除或业务数据库工具。
""".strip()


def create_server(database_path: Path | str | None = None) -> MCPServer:
    tools = IntakeSpecTools(TaskStateRepository(Database(database_path)))
    server = MCPServer("intake_spec_mcp", instructions=SERVER_INSTRUCTIONS)

    @server.tool()
    def read_task_context(
        task_id: str,
        requirement_revision: int | None = None,
        task_spec_version: int | None = None,
    ) -> ToolResponse:
        """读取当前任务或指定版本的最小 RequirementRecord 与 TaskSpec 上下文。"""
        return tools.read_task_context(task_id, requirement_revision, task_spec_version)

    @server.tool()
    def read_policy(policy_ref: str) -> ToolResponse:
        """读取 allowlist 内公开策略；未知引用默认拒绝。"""
        return tools.read_policy(policy_ref)

    @server.tool()
    def validate_requirement_record(payload: dict[str, Any]) -> ToolResponse:
        """确定性校验 RequirementRecord，不保存数据。"""
        return tools.validate_requirement_record(payload)

    @server.tool()
    def validate_task_spec(payload: dict[str, Any]) -> ToolResponse:
        """确定性校验 TaskSpec、验收覆盖、权限和阻塞状态，不保存数据。"""
        return tools.validate_task_spec(payload)

    @server.tool()
    def preflight_store_task_spec(
        task_id: str,
        payload: dict[str, Any],
        expected_requirement_revision: int,
        expected_task_spec_version: int,
    ) -> ToolResponse:
        """写入前检查真实版本，并返回规范化后的正式内部引用。"""
        return tools.preflight_store_task_spec(
            task_id,
            payload,
            expected_requirement_revision,
            expected_task_spec_version,
        )

    @server.tool()
    def store_task_spec(
        task_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        expected_requirement_revision: int,
        expected_task_spec_version: int,
    ) -> ToolResponse:
        """以追加版本方式原子保存 RequirementRecord 与可选 TaskSpec。"""
        return tools.store_task_spec(
            task_id,
            payload,
            idempotency_key,
            expected_requirement_revision,
            expected_task_spec_version,
        )

    @server.tool()
    def initialize_confirmed_task_spec(
        task_id: str,
        reviewed_payload: dict[str, Any],
        confirmed_payload: dict[str, Any],
        idempotency_key: str,
    ) -> ToolResponse:
        """一次原子事务保存新任务的受审 v1 与已确认 READY v2。"""
        return tools.initialize_confirmed_task_spec(
            task_id,
            reviewed_payload,
            confirmed_payload,
            idempotency_key,
        )

    return server


def main() -> int:
    create_server().run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
