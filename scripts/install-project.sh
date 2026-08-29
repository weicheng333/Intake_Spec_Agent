#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$(command -v python3.11 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "安装失败：需要 Python 3.11 或更高版本。" >&2
  exit 1
fi

PROJECT_ROOT="${1:-$PWD}"
exec "$PYTHON_BIN" "$PACKAGE_ROOT/scripts/package_manager.py" install --scope project --project-root "$PROJECT_ROOT" --python "$PYTHON_BIN"
