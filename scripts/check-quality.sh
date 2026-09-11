#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

for command in npm uv; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'missing required command: %s\n' "$command" >&2
        exit 1
    fi
done

cd "$repo_root"
printf '%s\n' '== install locked Python dependencies =='
uv sync --project server --locked --extra dev
printf '%s\n' '== server quality =='
bash scripts/check-server.sh
printf '%s\n' '== deployment checks =='
bash scripts/check-deploy.sh
printf '%s\n' '== install locked npm dependencies =='
npm ci --prefix web
printf '%s\n' '== frontend unit tests =='
npm --prefix web test
printf '%s\n' '== frontend production build =='
npm --prefix web run build
