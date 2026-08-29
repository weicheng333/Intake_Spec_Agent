#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$(command -v python3.11 || command -v python3)"

PURGE_ARGUMENT=""
if [[ "${1:-}" == "--purge-data" ]]; then
  PURGE_ARGUMENT="--purge-data"
  shift
fi
PROJECT_ROOT="${1:-$PWD}"

ARGS=(uninstall --scope project --project-root "$PROJECT_ROOT")
if [[ -n "$PURGE_ARGUMENT" ]]; then
  ARGS+=("$PURGE_ARGUMENT")
fi
exec "$PYTHON_BIN" "$PACKAGE_ROOT/scripts/package_manager.py" "${ARGS[@]}"
