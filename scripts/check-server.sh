#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python="${PYTHON:-$repo_root/server/.venv/bin/python}"
ruff="${RUFF:-$repo_root/server/.venv/bin/ruff}"

if [[ ! -x "$python" ]]; then
    printf 'missing Python environment: %s\n' "$python" >&2
    printf 'create it with: uv venv server/.venv && uv pip install -p server/.venv -e "server[dev]"\n' >&2
    exit 1
fi
if [[ ! -x "$ruff" ]]; then
    printf 'missing Ruff executable: %s\n' "$ruff" >&2
    printf 'install the server dev extra before running this command\n' >&2
    exit 1
fi

cd "$repo_root"
coverage_dir="$(mktemp -d "${TMPDIR:-/tmp}/arkham-server-quality.XXXXXX")"
trap 'rm -rf "$coverage_dir"' EXIT

COVERAGE_FILE="$coverage_dir/.coverage" "$python" -m pytest server -q \
    --cov=server/app \
    --cov-branch \
    --cov-report=term-missing \
    --cov-fail-under=90
"$ruff" check --no-cache server/app server/tests
"$ruff" format --check --no-cache server/app server/tests
