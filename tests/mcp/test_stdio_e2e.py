import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


def test_stdio_server_lists_and_calls_tools(tmp_path: Path) -> None:
    async def exercise() -> None:
        environment = os.environ.copy()
        environment["INTAKE_SPEC_DATA_DIR"] = str(tmp_path / "data")
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "intake_spec_agent.mcp_server.server"],
            cwd=Path(__file__).parents[2],
            env=environment,
        )
        async with Client(parameters, read_timeout_seconds=10) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {
                "read_task_context",
                "read_policy",
                "validate_requirement_record",
                "validate_task_spec",
                "store_task_spec",
            }
            result = await client.call_tool(
                "read_policy", {"policy_ref": "policy://intake-spec/default"}
            )
            assert result.is_error is False
            assert result.structured_content is not None
            assert result.structured_content["status"] == "SUCCESS"

    asyncio.run(exercise())
