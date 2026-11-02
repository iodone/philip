#!/usr/bin/env bash
# Run the checks documented in AGENTS.md against the repository's src layout.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "=== philip check @ $(git rev-parse --short HEAD) ==="

if ! command -v uv >/dev/null 2>&1; then
  echo "SKIP: uv not found"
  exit 2
fi

echo "--- deps: uv sync --group dev --frozen ---"
uv sync --group dev --frozen

echo "--- format: black --check . ---"
uv run black --check .

echo "--- lint: ruff check . ---"
uv run ruff check .

echo "--- type-check: mypy src/philip ---"
uv run mypy src/philip

echo "--- test: pytest ---"
uv run pytest

echo "--- build: uv build ---"
uv build

echo "PASS"
