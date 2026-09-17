#!/usr/bin/env python3
"""Intake & Spec Agent 的全局/项目安装与卸载实现。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

from merge_codex_config import install_config, uninstall_config

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.2.1"


class PackageManagerError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallLayout:
    scope: Literal["global", "project"]
    codex_root: Path
    agents_root: Path
    install_root: Path
    runtime: Path
    data: Path
    agent: Path
    skill: Path
    config: Path
    manifest: Path


def resolve_layout(scope: Literal["global", "project"], project_root: Path | None) -> InstallLayout:
    if scope == "global":
        codex_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        agents_root = Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents")).expanduser()
        data = Path(
            os.environ.get(
                "INTAKE_SPEC_DATA_DIR", Path.home() / ".local" / "share" / "intake-spec-agent"
            )
        ).expanduser()
    else:
        root = (project_root or Path.cwd()).expanduser().resolve()
        codex_root = root / ".codex"
        agents_root = root / ".agents"
        data = codex_root / "intake-spec-agent" / "data"
    install_root = codex_root / "intake-spec-agent"
    return InstallLayout(
        scope=scope,
        codex_root=codex_root,
        agents_root=agents_root,
        install_root=install_root,
        runtime=install_root / "runtime",
        data=data,
        agent=codex_root / "agents" / "intake_spec.toml",
        skill=agents_root / "skills" / "intake-spec",
        config=codex_root / "config.toml",
        manifest=install_root / "install-manifest.json",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise PackageManagerError(f"拒绝覆盖符号链接：{path}")


def _replace_file(source: Path, destination: Path) -> Path | None:
    _reject_symlink(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if destination.exists():
        backup = destination.with_name(f".{destination.name}.backup-{uuid4().hex}")
        os.replace(destination, backup)
    temporary = destination.with_name(f".{destination.name}.new-{uuid4().hex}")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        if backup is not None:
            os.replace(backup, destination)
        raise
    return backup


def _replace_directory(source: Path, destination: Path) -> Path | None:
    _reject_symlink(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.new-{uuid4().hex}"
    shutil.copytree(source, temporary)
    backup = None
    try:
        if destination.exists():
            backup = destination.parent / f".{destination.name}.backup-{uuid4().hex}"
            os.replace(destination, backup)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and not destination.exists():
            os.replace(backup, destination)
        raise
    return backup


def _restore_replacement(destination: Path, backup: Path | None) -> None:
    if destination.is_dir():
        shutil.rmtree(destination)
    else:
        destination.unlink(missing_ok=True)
    if backup is not None and backup.exists():
        os.replace(backup, destination)


def _discard_backup(backup: Path | None) -> None:
    if backup is None:
        return
    if backup.is_dir():
        shutil.rmtree(backup)
    else:
        backup.unlink(missing_ok=True)


def _build_runtime(source_root: Path, destination: Path, python_executable: Path) -> Path | None:
    _reject_symlink(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".intake-spec-runtime-", dir=destination.parent))
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(source_root / name, staging / name)
    for name in ("src", "contracts"):
        shutil.copytree(source_root / name, staging / name)

    backup = None
    try:
        if destination.exists():
            backup = destination.parent / f".{destination.name}.backup-{uuid4().hex}"
            os.replace(destination, backup)
        os.replace(staging, destination)
        subprocess.run(
            [str(python_executable), "-m", "venv", str(destination / ".venv")],
            check=True,
        )
        subprocess.run(
            [
                str(destination / ".venv" / "bin" / "python"),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                str(destination),
            ],
            check=True,
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        if backup is not None:
            os.replace(backup, destination)
        raise
    return backup


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


RuntimeBuilder = Callable[[Path, Path, Path], Path | None]


def install_package(
    layout: InstallLayout,
    python_executable: Path,
    *,
    runtime_builder: RuntimeBuilder = _build_runtime,
) -> dict:
    required = [
        PACKAGE_ROOT / "pyproject.toml",
        PACKAGE_ROOT / ".codex" / "agents" / "intake_spec.toml",
        PACKAGE_ROOT / ".agents" / "skills" / "intake-spec" / "SKILL.md",
        PACKAGE_ROOT / "contracts" / "task-spec.schema.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise PackageManagerError(f"安装包缺少文件：{missing}")
    if not python_executable.exists():
        raise PackageManagerError(f"未找到 Python：{python_executable}")

    layout.install_root.mkdir(parents=True, exist_ok=True)
    layout.data.mkdir(parents=True, exist_ok=True)
    config_existed = layout.config.exists()
    config_original = layout.config.read_bytes() if config_existed else None
    replacements: list[tuple[Path, Path | None]] = []
    try:
        replacements.append(
            (layout.runtime, runtime_builder(PACKAGE_ROOT, layout.runtime, python_executable))
        )
        replacements.append(
            (
                layout.agent,
                _replace_file(PACKAGE_ROOT / ".codex" / "agents" / "intake_spec.toml", layout.agent),
            )
        )
        replacements.append(
            (
                layout.skill,
                _replace_directory(PACKAGE_ROOT / ".agents" / "skills" / "intake-spec", layout.skill),
            )
        )
        runtime_python = layout.runtime / ".venv" / "bin" / "python"
        install_config(
            layout.config,
            runtime_python=runtime_python,
            runtime_directory=layout.runtime,
            data_directory=layout.data,
        )
        manifest = {
            "version": VERSION,
            "scope": layout.scope,
            "config_existed_before": config_existed,
            "paths": {
                "runtime": str(layout.runtime),
                "data": str(layout.data),
                "agent": str(layout.agent),
                "skill": str(layout.skill),
                "config": str(layout.config),
            },
            "ownership": {
                "agent_sha256": _sha256_file(layout.agent),
                "skill_sha256": _sha256_tree(layout.skill),
            },
        }
        _atomic_json(layout.manifest, manifest)
    except Exception:
        if config_existed and config_original is not None:
            layout.config.parent.mkdir(parents=True, exist_ok=True)
            layout.config.write_bytes(config_original)
        elif not config_existed:
            layout.config.unlink(missing_ok=True)
        for destination, backup in reversed(replacements):
            _restore_replacement(destination, backup)
        raise
    for _, backup in replacements:
        _discard_backup(backup)
    return manifest


def _safe_owned_delete(path: Path, protected: set[Path]) -> None:
    resolved = path.expanduser().resolve()
    if resolved in protected or resolved == Path.home().resolve() or resolved == Path("/"):
        raise PackageManagerError(f"拒绝删除宽泛路径：{resolved}")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def uninstall_package(layout: InstallLayout, *, purge_data: bool = False) -> list[str]:
    messages: list[str] = []
    manifest = None
    if layout.manifest.exists():
        manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))

    uninstall_config(layout.config)
    if manifest is None:
        messages.append("未找到安装清单；未删除 Agent、Skill、runtime 或数据")
        return messages

    ownership = manifest.get("ownership", {})
    if layout.agent.exists():
        if _sha256_file(layout.agent) == ownership.get("agent_sha256"):
            layout.agent.unlink()
        else:
            messages.append(f"Agent 已被修改，保留：{layout.agent}")
    if layout.skill.exists():
        if _sha256_tree(layout.skill) == ownership.get("skill_sha256"):
            shutil.rmtree(layout.skill)
        else:
            messages.append(f"Skill 已被修改，保留：{layout.skill}")

    protected = {layout.codex_root.resolve(), layout.agents_root.resolve(), layout.install_root.resolve()}
    if layout.runtime.exists():
        _safe_owned_delete(layout.runtime, protected)
    layout.manifest.unlink(missing_ok=True)
    if purge_data and layout.data.exists():
        _safe_owned_delete(layout.data, protected)
        messages.append(f"已彻底清理数据：{layout.data}")
    else:
        messages.append(f"已保留数据：{layout.data}")

    if not manifest.get("config_existed_before", True) and layout.config.exists():
        if not layout.config.read_text(encoding="utf-8").strip():
            layout.config.unlink()
    try:
        layout.install_root.rmdir()
    except OSError:
        pass
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--scope", choices=["global", "project"], required=True)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--purge-data", action="store_true")
    arguments = parser.parse_args()
    if arguments.scope == "global" and arguments.project_root is not None:
        parser.error("global 安装不能指定 --project-root")
    if arguments.action == "install" and arguments.purge_data:
        parser.error("--purge-data 只适用于卸载")
    layout = resolve_layout(arguments.scope, arguments.project_root)
    try:
        if arguments.action == "install":
            manifest = install_package(layout, arguments.python)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
        else:
            for message in uninstall_package(layout, purge_data=arguments.purge_data):
                print(message)
    except (PackageManagerError, subprocess.CalledProcessError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
