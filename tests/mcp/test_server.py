import asyncio
from pathlib import Path

from intake_spec_agent.mcp_server import create_server

EXPECTED_TOOLS = {
    "read_task_context",
    "read_policy",
    "validate_requirement_record",
    "validate_task_spec",
    "preflight_store_task_spec",
    "store_task_spec",
    "initialize_confirmed_task_spec",
}


def test_server_exposes_only_allowlisted_tools(tmp_path: Path) -> None:
    server = create_server(tmp_path / "state.sqlite3")
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_tool_schemas_are_typed(tmp_path: Path) -> None:
    server = create_server(tmp_path / "state.sqlite3")
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    assert tools["read_task_context"].input_schema["required"] == ["task_id"]
    assert set(tools["store_task_spec"].input_schema["required"]) == {
        "task_id",
        "payload",
        "idempotency_key",
        "expected_requirement_revision",
        "expected_task_spec_version",
    }
    assert set(tools["initialize_confirmed_task_spec"].input_schema["required"]) == {
        "task_id",
        "reviewed_payload",
        "confirmed_payload",
        "idempotency_key",
    }
    assert tools["read_policy"].output_schema["properties"]["status"]["enum"] == [
        "SUCCESS",
        "ERROR",
    ]


def test_server_returns_structured_content(tmp_path: Path) -> None:
    server = create_server(tmp_path / "state.sqlite3")
    result = asyncio.run(
        server.call_tool("read_policy", {"policy_ref": "policy://intake-spec/default"})
    )
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["status"] == "SUCCESS"
    assert result.structured_content["evidence_ref"].startswith("evidence://policy/sha256/")
