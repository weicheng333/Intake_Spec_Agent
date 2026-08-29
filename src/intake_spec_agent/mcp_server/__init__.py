"""Intake & Spec Agent MCP 服务。"""

from pathlib import Path
from typing import Any

from .tools import IntakeSpecTools, ToolResponse

__all__ = ["IntakeSpecTools", "ToolResponse", "create_server"]


def create_server(database_path: Path | str | None = None) -> Any:
    """延迟导入服务入口，避免以 ``python -m`` 启动时重复加载模块。"""
    from .server import create_server as factory

    return factory(database_path)
