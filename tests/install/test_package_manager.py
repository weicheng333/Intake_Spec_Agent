import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from package_manager import install_package, resolve_layout, uninstall_package


def _fake_runtime_builder(source: Path, destination: Path, python: Path) -> Path | None:
    del source, python
    backup = None
    if destination.exists():
        backup = destination.parent / f".runtime-test-backup-{uuid4().hex}"
        os.replace(destination, backup)
    (destination / ".venv" / "bin").mkdir(parents=True)
    (destination / ".venv" / "bin" / "python").write_text("test runtime")
    return backup


def test_project_install_and_uninstall_preserve_other_agent_and_data(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    (project / ".codex" / "agents").mkdir(parents=True)
    (project / ".agents" / "skills" / "requirement-clarification").mkdir(parents=True)
    old_agent = project / ".codex" / "agents" / "requirement-clarifier.toml"
    old_skill = project / ".agents" / "skills" / "requirement-clarification" / "SKILL.md"
    old_agent.write_text('name = "requirement_clarifier"\n')
    old_skill.write_text("old skill")
    config = project / ".codex" / "config.toml"
    config.write_text('[mcp_servers.requirement]\ncommand = "node"\n')
    layout = resolve_layout("project", project)

    first = install_package(layout, Path(sys.executable), runtime_builder=_fake_runtime_builder)
    second = install_package(layout, Path(sys.executable), runtime_builder=_fake_runtime_builder)
    (layout.data / "keep.sqlite3").write_text("user data")

    assert first["version"] == "1.1.0"
    assert second["version"] == "1.1.0"
    assert layout.agent.exists() and layout.skill.exists() and layout.manifest.exists()
    assert "intake_spec_mcp" in config.read_text()
    messages = uninstall_package(layout)

    assert old_agent.exists() and old_skill.exists()
    assert "[mcp_servers.requirement]" in config.read_text()
    assert "intake_spec_mcp" not in config.read_text()
    assert not layout.agent.exists() and not layout.skill.exists() and not layout.runtime.exists()
    assert (layout.data / "keep.sqlite3").exists()
    assert any("已保留数据" in message for message in messages)


def test_uninstall_preserves_modified_skill(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    layout = resolve_layout("project", project)
    install_package(layout, Path(sys.executable), runtime_builder=_fake_runtime_builder)
    with (layout.skill / "SKILL.md").open("a") as handle:
        handle.write("\nuser modification\n")

    messages = uninstall_package(layout)
    assert layout.skill.exists()
    assert any("Skill 已被修改" in message for message in messages)


def test_purge_removes_only_package_data(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    unrelated = project / "keep.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("keep")
    layout = resolve_layout("project", project)
    install_package(layout, Path(sys.executable), runtime_builder=_fake_runtime_builder)
    (layout.data / "state.sqlite3").write_text("state")

    messages = uninstall_package(layout, purge_data=True)
    assert not layout.data.exists()
    assert unrelated.exists()
    assert any("已彻底清理数据" in message for message in messages)
