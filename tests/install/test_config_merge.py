from pathlib import Path

import pytest

from merge_codex_config import ConfigMergeError, install_config, uninstall_config


def test_install_preserves_existing_config_and_is_idempotent(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('model = "existing"\n\n[mcp_servers.other]\ncommand = "other"\n')

    backup = install_config(
        config,
        runtime_python=tmp_path / "runtime/.venv/bin/python",
        runtime_directory=tmp_path / "runtime",
        data_directory=tmp_path / "data",
    )
    first = config.read_text()
    second_backup = install_config(
        config,
        runtime_python=tmp_path / "runtime/.venv/bin/python",
        runtime_directory=tmp_path / "runtime",
        data_directory=tmp_path / "data",
    )

    assert backup is not None and backup.exists()
    assert second_backup is None
    assert config.read_text() == first
    assert 'model = "existing"' in first
    assert "[mcp_servers.other]" in first
    assert "[mcp_servers.intake_spec_mcp]" in first


def test_uninstall_removes_only_managed_block(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[mcp_servers.other]\ncommand = "other"\n')
    install_config(
        config,
        runtime_python=tmp_path / "runtime/.venv/bin/python",
        runtime_directory=tmp_path / "runtime",
        data_directory=tmp_path / "data",
    )
    uninstall_config(config)
    content = config.read_text()
    assert "[mcp_servers.other]" in content
    assert "intake_spec_mcp" not in content


def test_invalid_toml_is_not_rewritten(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    invalid = "[broken\n"
    config.write_text(invalid)
    with pytest.raises(ConfigMergeError, match="无法安全解析 TOML"):
        install_config(
            config,
            runtime_python=tmp_path / "python",
            runtime_directory=tmp_path / "runtime",
            data_directory=tmp_path / "data",
        )
    assert config.read_text() == invalid


def test_unmanaged_conflicting_table_is_not_overwritten(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    original = '[mcp_servers.intake_spec_mcp]\ncommand = "user-owned"\n'
    config.write_text(original)
    with pytest.raises(ConfigMergeError, match="拒绝覆盖"):
        install_config(
            config,
            runtime_python=tmp_path / "python",
            runtime_directory=tmp_path / "runtime",
            data_directory=tmp_path / "data",
        )
    assert config.read_text() == original


def test_broken_ownership_markers_are_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("# BEGIN intake-spec-agent managed MCP\n")
    with pytest.raises(ConfigMergeError, match="标记不完整"):
        uninstall_config(config)
