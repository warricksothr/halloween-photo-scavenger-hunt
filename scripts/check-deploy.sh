#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python="${PYTHON:-$repo_root/server/.venv/bin/python}"

if [[ ! -x "$python" ]]; then
    printf 'missing Python environment: %s\n' "$python" >&2
    printf 'create it with: uv venv server/.venv && uv pip install -p server/.venv -e "server[dev]"\n' >&2
    exit 1
fi

cd "$repo_root"
bash -n deploy/backup.sh scripts/build-pages.sh scripts/check-deploy.sh scripts/smoke-container.sh
"$python" -m pytest server/tests/test_deployment_checks.py -q
