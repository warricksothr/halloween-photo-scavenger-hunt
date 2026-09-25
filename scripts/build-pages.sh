#!/usr/bin/env bash
# Assemble the GitHub Pages site into OUT_DIR (docs/site/README.md).
#
#   bash scripts/build-pages.sh OUT_DIR
#
# The site is three things from main, copied as they are: the project page
# (docs/site/index.html), the README screenshots (docs/screenshots), and the
# design-phase mocks (docs/impl/mocks) under mocks/. Nothing is generated,
# so the published files are always ones that are reviewed on main.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:?usage: build-pages.sh OUT_DIR}"

# An empty or missing directory only: the publish step replaces the whole
# branch with OUT_DIR, and a leftover file would be published with it.
if [[ -e "$out" ]] && [[ -n "$(ls -A -- "$out")" ]]; then
    printf 'refusing to build into a non-empty directory: %s\n' "$out" >&2
    exit 1
fi

mkdir -p "$out/screenshots" "$out/mocks"
cp "$repo_root/docs/site/index.html" "$out/index.html"
cp "$repo_root"/docs/screenshots/*.png "$out/screenshots/"
cp -R "$repo_root/docs/impl/mocks/." "$out/mocks/"
# Serve files as they are: without this, Pages runs Jekyll over the tree.
: > "$out/.nojekyll"
printf 'built %s\n' "$out"
