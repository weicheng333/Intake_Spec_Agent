#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$(command -v python3.11 || command -v python3)"

exec "$PYTHON_BIN" "$PACKAGE_ROOT/scripts/package_manager.py" uninstall --scope global "$@"
