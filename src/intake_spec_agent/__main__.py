"""Intake & Spec Agent 命令行入口。"""

from __future__ import annotations

from . import __version__


def main() -> int:
    """输出当前版本；正式 MCP 入口将在后续阶段接入。"""
    print(f"Intake & Spec Agent {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
