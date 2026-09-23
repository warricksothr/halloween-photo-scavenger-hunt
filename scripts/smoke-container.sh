#!/usr/bin/env bash
# Disposable raw-Podman smoke for the local HTTP container recipe.
#
# This is intentionally opt-in. The fast checks do not need a container
# runtime; run this script when Podman and Chromium-like host networking are
# available. Failure logs remain under .deploy-smoke-results/.

set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runtime="${CONTAINER_RUNTIME:-podman}"
python="${PYTHON:-$repo_root/server/.venv/bin/python}"
run_id="${ARKHAM_SMOKE_RUN_ID:-$(date +%Y%m%d-%H%M%S)-$$}"
image="arkham-hunt-smoke:${run_id}"
container="arkham-hunt-smoke-${run_id}"
volume="arkham-data-smoke-${run_id}"
artifact_root="${ARKHAM_SMOKE_ARTIFACT_DIR:-$repo_root/.deploy-smoke-results}"
artifact_dir="$artifact_root/$run_id"

for command in "$runtime" cp curl date grep mkdir mktemp rm seq sleep tee; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'missing required command: %s\n' "$command" >&2
        exit 1
    fi
done
if [[ ! -x "$python" ]]; then
    printf 'missing Python environment: %s\n' "$python" >&2
    exit 1
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/arkham-container-smoke.XXXXXX")"
admin_jar="$work/admin.jar"
player_jar="$work/player.jar"

cleanup() {
    status=$?
    set +e
    if ((status != 0)); then
        mkdir -p "$artifact_dir"
        "$runtime" logs "$container" >"$artifact_dir/container.log" 2>&1
        "$runtime" inspect "$container" >"$artifact_dir/container.inspect.json" 2>&1
        cp "$work/smoke.log" "$artifact_dir/smoke.log" 2>/dev/null || true
        printf 'container smoke failed; diagnostics: %s\n' "$artifact_dir" >&2
    fi
    "$runtime" rm --force "$container" >/dev/null 2>&1 || true
    "$runtime" volume rm "$volume" >/dev/null 2>&1 || true
    "$runtime" rmi "$image" >/dev/null 2>&1 || true
    rm -rf "$work"
    if ((status == 0)); then
        rm -rf "$artifact_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

# Keep the command transcript until cleanup decides whether it is a failure
# artifact. The container log is captured separately before the container is
# removed.
exec > >(tee "$work/smoke.log") 2>&1

printf 'building %s\n' "$image"
"$runtime" build --format docker --tag "$image" "$repo_root"
"$runtime" volume create "$volume" >/dev/null

admin_user="container-smoke-admin"
admin_password="$("$python" -c 'import secrets; print(secrets.token_urlsafe(24))')"
admin_hash="$("$python" -m app.security "$admin_password")"
port="$("$python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
base_url="http://127.0.0.1:$port"

printf 'starting %s on %s\n' "$container" "$base_url"
"$runtime" run --detach \
    --name "$container" \
    --publish "127.0.0.1:$port:8000" \
    --env "ARKHAM_ADMIN_USERNAME=$admin_user" \
    --env "ARKHAM_ADMIN_PASSWORD_HASH=$admin_hash" \
    --env ARKHAM_COOKIE_SECURE=false \
    --volume "$volume:/srv/arkham/data" \
    "$image" >/dev/null

printf 'waiting for health endpoint\n'
for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error "$base_url/api/health" >"$work/health.json"; then
        break
    fi
    if ((attempt == 60)); then
        printf 'health endpoint did not respond\n' >&2
        exit 1
    fi
    sleep 1
done
"$python" -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"' <"$work/health.json"

for attempt in $(seq 1 30); do
    health="$($runtime inspect "$container" --format '{{.State.Health.Status}}')"
    if [[ "$health" == healthy ]]; then
        break
    fi
    if ((attempt == 30)); then
        printf 'container health status is %s\n' "$health" >&2
        exit 1
    fi
    sleep 1
done

json_value() {
    "$python" -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

printf 'logging in as disposable admin\n'
login_json="$(curl --fail --silent --show-error \
    --cookie-jar "$admin_jar" \
    --header 'Content-Type: application/json' \
    --data "{\"username\":\"$admin_user\",\"password\":\"$admin_password\"}" \
    "$base_url/api/admin/login")"
printf '%s' "$login_json" | "$python" -c 'import json, sys; assert json.load(sys.stdin)["ok"] is True'

ready_json="$(curl --fail --silent --show-error \
    --cookie "$admin_jar" --cookie-jar "$admin_jar" \
    "$base_url/api/admin/readyz")"
printf '%s' "$ready_json" | "$python" -c 'import json, sys; body = json.load(sys.stdin); assert body["status"] == "ok" and body["db_writable"] is True and body["schema_version"] >= 1'

event_json="$(curl --fail --silent --show-error \
    --cookie "$admin_jar" --cookie-jar "$admin_jar" \
    --header 'Content-Type: application/json' \
    --data '{"name":"Container Smoke"}' \
    "$base_url/api/admin/events")"
event_id="$(printf '%s' "$event_json" | json_value id)"
join_code="$(printf '%s' "$event_json" | json_value join_code)"

curl --fail --silent --show-error \
    --cookie "$admin_jar" --cookie-jar "$admin_jar" \
    --header 'Content-Type: application/json' \
    --data '{"text":"Find the smoke signal","sort_order":1}' \
    "$base_url/api/admin/events/$event_id/riddles" >/dev/null
curl --fail --silent --show-error --request POST \
    --cookie "$admin_jar" --cookie-jar "$admin_jar" \
    "$base_url/api/admin/events/$event_id/open" >/dev/null

printf 'joining player over plain HTTP\n'
join_json="$(curl --fail --silent --show-error \
    --cookie-jar "$player_jar" \
    --header 'Content-Type: application/json' \
    --data '{"display_name":"Smoke Player","device_label":"smoke phone"}' \
    "$base_url/api/join/$join_code")"
printf '%s' "$join_json" | "$python" -c 'import json, sys; assert json.load(sys.stdin)["event"]["status"] == "open"'

# Upload one synthetic photo so the cleanup path removes both generated
# derivatives and quarantined originals from the disposable volume.
photo_path="$work/smoke.jpg"
"$python" -c 'from PIL import Image; import sys; Image.new("RGB", (32, 32), (30, 90, 140)).save(sys.argv[1], "JPEG")' "$photo_path"
photo_json="$(curl --fail --silent --show-error \
    --cookie "$player_jar" \
    --form "photo=@$photo_path;type=image/jpeg" \
    "$base_url/api/evidence")"
printf '%s' "$photo_json" | "$python" -c 'import json, sys; assert json.load(sys.stdin)["id"]'

printf 'waiting for SSE heartbeat\n'
set +e
curl --no-buffer --silent --show-error --max-time 18 \
    --cookie "$player_jar" "$base_url/api/events/stream" >"$work/sse.txt"
sse_status=$?
set -e
if [[ "$sse_status" -ne 0 && "$sse_status" -ne 28 ]]; then
    printf 'SSE request failed with curl status %s\n' "$sse_status" >&2
    exit 1
fi
grep -q ': heartbeat' "$work/sse.txt"
printf 'container smoke passed\n'
