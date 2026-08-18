#!/bin/sh
# backup.sh — one-command backup of the night's state (design.md:
# "the worst realistic incident is losing the SQLite file or photos
# mid-party"). Produces one timestamped tarball beside the repo by
# default; pass a destination directory to override.
#
#   ./deploy/backup.sh [dest-dir]
#
# Restore (see deploy/RUNBOOK.md for the full drill):
#   systemctl --user stop arkham-hunt
#   tar -xzf arkham-backup-*.tar.gz -C <repo-root>
#   systemctl --user start arkham-hunt
#
# The DB snapshot uses Python's sqlite3 backup API (online, WAL-safe)
# — the server venv always has it, so the script does not depend on the
# sqlite3 CLI package being installed on the host. Falls back to the
# CLI if for some reason no Python is found.

set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
DEST_DIR="${1:-$REPO_ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$DEST_DIR/.backup-work-$STAMP"
OUT="$DEST_DIR/arkham-backup-$STAMP.tar.gz"

if [ ! -f "$DATA_DIR/arkham.db" ]; then
    echo "no database at $DATA_DIR/arkham.db — nothing to back up" >&2
    exit 1
fi

mkdir -p "$WORK/photos"
PY="$REPO_ROOT/server/.venv/bin/python"
if [ -x "$PY" ]; then :; elif command -v python3 >/dev/null; then PY=python3; else PY=""; fi
if [ -n "$PY" ]; then
    "$PY" -c "
import sqlite3
src = sqlite3.connect('$DATA_DIR/arkham.db')
dst = sqlite3.connect('$WORK/arkham.db')
src.backup(dst)
dst.close(); src.close()
"
elif command -v sqlite3 >/dev/null; then
    sqlite3 "$DATA_DIR/arkham.db" ".backup '$WORK/arkham.db'"
else
    echo "need python3 or sqlite3 for the online backup" >&2
    exit 1
fi
[ -d "$DATA_DIR/photos" ] && cp -r "$DATA_DIR/photos/." "$WORK/photos/"

tar -czf "$OUT" -C "$WORK" arkham.db photos
rm -rf "$WORK"
echo "backup written: $OUT"
