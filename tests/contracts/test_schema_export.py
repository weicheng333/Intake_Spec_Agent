import json
from pathlib import Path

from intake_spec_agent.contracts.export_schemas import SCHEMAS, export_schemas


def test_schema_export_is_complete_and_deterministic(tmp_path: Path) -> None:
    first_paths = export_schemas(tmp_path)
    first_contents = {path.name: path.read_text(encoding="utf-8") for path in first_paths}
    second_paths = export_schemas(tmp_path)
    second_contents = {path.name: path.read_text(encoding="utf-8") for path in second_paths}

    assert set(first_contents) == set(SCHEMAS)
    assert first_contents == second_contents
    for content in first_contents.values():
        schema = json.loads(content)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False


def test_committed_schemas_match_models(tmp_path: Path) -> None:
    generated_paths = export_schemas(tmp_path)
    project_contracts = Path(__file__).parents[2] / "contracts"

    for generated in generated_paths:
        committed = project_contracts / generated.name
        assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")
