"""导出供其他 Agent 使用的 JSON Schema。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .handoff import AgentMessage, HandoffEnvelope, IntakeSpecRoleOutput
from .requirement_record import RequirementRecord
from .task_spec import TaskSpec

SCHEMAS = {
    "agent-message.schema.json": AgentMessage,
    "handoff.schema.json": HandoffEnvelope,
    "requirement-record.schema.json": RequirementRecord,
    "role-output.schema.json": IntakeSpecRoleOutput,
    "task-spec.schema.json": TaskSpec,
}


def export_schemas(output_directory: Path) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in SCHEMAS.items():
        path = output_directory / filename
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://schemas.intake-spec-agent.local/v1/{filename}"
        content = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
        path.write_text(f"{content}\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 Intake & Spec Agent JSON Schema")
    parser.add_argument("--output", type=Path, default=Path("contracts"))
    arguments = parser.parse_args()
    for path in export_schemas(arguments.output):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
