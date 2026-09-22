#!/bin/sh
# backup.sh — one-command backup of the night's state (design.md:
# "the worst realistic incident is losing the SQLite file or photos
# mid-party"). Produces one timestamped tarball in backups/ by default;
# pass a destination directory to override.
#
#   ./deploy/backup.sh [dest-dir]
#
# Set ARKHAM_BACKUP_MIRROR to a directory on another disk (a USB drive,
# an NFS mount, a synced folder) to keep a copy off the host, and
# ARKHAM_BACKUP_KEEP to bound how many archives each directory retains
# (default 14). Without a mirror the script warns: a backup on the same
# disk is not a backup.
#
# Restore (see deploy/RUNBOOK.md §1 for the full drill):
#   systemctl --user stop arkham-hunt
#   tar -xzf backups/arkham-backup-*.tar.gz -C <repo-root>/data
#   systemctl --user start arkham-hunt
#
# The archive holds arkham.db and photos/ at its root, and the app reads
# <repo-root>/data — extract into data/, not the repo root, or the
# database is silently empty.
#
# The DB snapshot uses Python's sqlite3 backup API (online, WAL-safe)
# — the server venv always has it, so the script does not depend on the
# sqlite3 CLI package being installed on the host. Falls back to the
# CLI if for some reason no Python is found.

set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# The override keeps isolated restore tests away from the repository's
# runtime data. Production uses the default repo-relative directory.
DATA_DIR="${ARKHAM_DATA_DIR:-$REPO_ROOT/data}"
DEST_DIR="${1:-$REPO_ROOT/backups}"
MIRROR="${ARKHAM_BACKUP_MIRROR:-}"
KEEP="${ARKHAM_BACKUP_KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

case "$KEEP" in
'' | *[!0-9]*)
    echo "ARKHAM_BACKUP_KEEP must be a non-negative integer: $KEEP" >&2
    exit 1
    ;;
esac

if [ ! -f "$DATA_DIR/arkham.db" ]; then
    echo "no database at $DATA_DIR/arkham.db — nothing to back up" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
# mktemp -d is atomic, so two backups in the same second get distinct
# work directories; the archive borrows the same suffix and cannot
# collide either.
WORK="$(mktemp -d "$DEST_DIR/.backup-work-$STAMP-XXXXXX")"
OUT="$DEST_DIR/arkham-backup-$STAMP-${WORK##*-}.tar.gz"

cleanup() {
    rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$WORK/photos"
PY="$REPO_ROOT/server/.venv/bin/python"
if [ -x "$PY" ]; then :; elif command -v python3 >/dev/null; then PY=python3; else PY=""; fi
if [ -n "$PY" ]; then
    ARKHAM_SOURCE_DB="$DATA_DIR/arkham.db" \
    ARKHAM_SNAPSHOT_DB="$WORK/arkham.db" \
    "$PY" -c '
import os
import sqlite3

with sqlite3.connect(os.environ["ARKHAM_SOURCE_DB"]) as src:
    with sqlite3.connect(os.environ["ARKHAM_SNAPSHOT_DB"]) as dst:
        src.backup(dst)
'
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

# Keep the newest $KEEP archives in a directory. Names sort
# chronologically because they start with the timestamp, so the first
# (total - keep) of them are the ones to drop.
prune() {
    dir="$1"
    total=0
    for archive in "$dir"/arkham-backup-*.tar.gz; do
        [ -e "$archive" ] || continue
        total=$((total + 1))
    done
    remove=$((total - KEEP))
    [ "$remove" -gt 0 ] || return 0
    seen=0
    for archive in "$dir"/arkham-backup-*.tar.gz; do
        [ -e "$archive" ] || continue
        seen=$((seen + 1))
        if [ "$seen" -le "$remove" ]; then
            rm -f "$archive"
        fi
    done
}

if [ -z "$MIRROR" ]; then
    echo "warning: ARKHAM_BACKUP_MIRROR is unset — this copy shares a disk with the data" >&2
else
    if [ ! -d "$MIRROR" ]; then
        echo "ARKHAM_BACKUP_MIRROR is not a directory: $MIRROR" >&2
        echo "(is the off-host mount actually mounted?)" >&2
        exit 1
    fi
    if command -v stat >/dev/null 2>&1 &&
        [ "$(stat -c %d -- "$MIRROR")" = "$(stat -c %d -- "$DATA_DIR")" ]; then
        echo "warning: ARKHAM_BACKUP_MIRROR is on the same device as the data" >&2
    fi
    # Mirror before pruning: a prune can drop this run's archive, and the
    # off-host copy must not depend on it surviving locally.
    cp "$OUT" "$MIRROR/"
    echo "backup mirrored: $MIRROR/${OUT##*/}"
fi

prune "$DEST_DIR"
[ -z "$MIRROR" ] || prune "$MIRROR"
