"""Seed a demo event through the admin HTTP API.

``python -m app.seed`` creates an event from a JSON fixture, adds its
riddles with their hint ladders, and opens the round. It prints the
join and mod codes so the host can hand them out.

It talks HTTP rather than SQL on purpose: the admin routes own the
audit rows, the hint ordering, and the open gate, and a seeder that
wrote rows directly would skip all three. It authenticates with the
admin API token (``ARKHAM_ADMIN_API_TOKEN``, RUNBOOK "Scripted access"),
so it needs no cookie jar and no CSRF pair.

It lives inside ``app`` so the container can run it as-is
(``podman exec <container> python -m app.seed``) and so the server's
quality gate covers it (ADR 0025).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

import httpx2
from pydantic import ValidationError

from app.auth import API_TOKEN_ENV
from app.events import EventCreate, RiddleCreate

DEFAULT_FIXTURE = Path(__file__).parent / "fixtures" / "demo-event.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class SeedError(Exception):
    """A failure the operator should read, printed without a traceback."""


def _reject_unknown(fields: dict, model: type, where: str) -> None:
    # The request models ignore extra keys, so a typo (or the old single
    # ``hint`` key) would drop content silently instead of failing.
    unknown = sorted(set(fields) - set(model.model_fields))
    if unknown:
        raise SeedError(f"{where} has unknown keys: {', '.join(unknown)}")


def validate_fixture(data: object) -> dict:
    """Check the whole fixture before the first write.

    The server would refuse a bad riddle anyway, but only after the event
    exists, which leaves a half-built event behind. Validating with the
    server's own request models keeps the two sets of limits identical.
    """
    if not isinstance(data, dict):
        raise SeedError("fixture must be a JSON object")
    riddles = data.get("riddles")
    if not isinstance(riddles, list) or not riddles:
        # The open route refuses an event with no riddles (409 no_riddles).
        raise SeedError("fixture needs a non-empty 'riddles' list")
    event_fields = {k: v for k, v in data.items() if k != "riddles"}
    _reject_unknown(event_fields, EventCreate, "fixture event")
    try:
        EventCreate.model_validate(event_fields)
    except ValidationError as exc:
        raise SeedError(f"fixture event is invalid: {exc}") from exc
    seen: set[int] = set()
    for index, riddle in enumerate(riddles, start=1):
        if not isinstance(riddle, dict):
            raise SeedError(f"fixture riddle {index} must be a JSON object")
        _reject_unknown(riddle, RiddleCreate, f"fixture riddle {index}")
        try:
            parsed = RiddleCreate.model_validate(riddle)
        except ValidationError as exc:
            raise SeedError(f"fixture riddle {index} is invalid: {exc}") from exc
        # The server allows ties (it falls back to created_at), but in a
        # fixture a repeated sort_order is a typo, not an intent.
        if parsed.sort_order in seen:
            raise SeedError(
                f"fixture riddle {index} repeats sort_order {parsed.sort_order}"
            )
        seen.add(parsed.sort_order)
    return data


def load_fixture(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SeedError(f"cannot read fixture {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"fixture {path} is not valid JSON: {exc}") from exc
    return validate_fixture(data)


def _call(client: httpx2.Client, method: str, path: str, **kwargs) -> object:
    """One API call; any non-2xx becomes a SeedError naming the route.

    Route errors are ``{"error", "message"}`` (api.md); auth dependencies
    raise ``HTTPException``, which FastAPI wraps as ``{"detail": {...}}``.
    Unwrap either, so the operator sees the code (``not_authenticated``,
    ``no_riddles``) rather than a bare status. Anything else (a proxy's
    HTML page, a 422 list) is shown raw and truncated.
    """
    try:
        resp = client.request(method, path, **kwargs)
    except httpx2.HTTPError as exc:
        raise SeedError(f"{method} {path} failed: {exc}") from exc
    if resp.is_success:
        return resp.json()
    try:
        body = resp.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("detail"), dict):
        body = body["detail"]
    if isinstance(body, dict) and "error" in body:
        detail = f"{body['error']}: {body.get('message')}"
        if body["error"] == "csrf_failed":
            # Only a matching token skips the CSRF check, so a wrong one
            # fails there first, on the first write, and the server's
            # "reload" advice is meant for a browser.
            detail += f"; the server did not accept the token in ${API_TOKEN_ENV}"
    else:
        detail = resp.text[:200]
    raise SeedError(f"{method} {path} answered {resp.status_code} ({detail})")


def seed(
    client: httpx2.Client,
    fixture: dict,
    *,
    open_round: bool = True,
    allow_duplicate: bool = False,
) -> dict:
    """Create the fixture's event and riddles; return the created event.

    ``client`` must already carry the base URL and the bearer header. The
    returned dict is the create response, so it holds the join and mod
    codes, with ``status`` updated if the round was opened.
    """
    fixture = validate_fixture(fixture)
    name = fixture["name"]
    if not allow_duplicate:
        # A rerun (a retried deploy, a second terminal) must not leave two
        # demo events with the same name for players to join by mistake.
        existing = [
            e for e in _call(client, "GET", "/api/admin/events") if e["name"] == name
        ]
        if existing:
            raise SeedError(
                f"an event named {name!r} already exists ({existing[0]['id']});"
                " pass --allow-duplicate to create another"
            )
    event_fields = {k: v for k, v in fixture.items() if k != "riddles"}
    event = _call(client, "POST", "/api/admin/events", json=event_fields)
    event_id = event["id"]
    for riddle in sorted(fixture["riddles"], key=lambda r: r["sort_order"]):
        _call(client, "POST", f"/api/admin/events/{event_id}/riddles", json=riddle)
    if open_round:
        opened = _call(client, "POST", f"/api/admin/events/{event_id}/open")
        event["status"] = opened["status"]
    return event


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="Create a demo event through the admin API.",
        epilog=f"Reads the admin API token from ${API_TOKEN_ENV}.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"server to seed (default {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="event JSON (default: the bundled demo event)",
    )
    parser.add_argument(
        "--no-open",
        dest="open_round",
        action="store_false",
        help="leave the event in the lobby, for a content review",
    )
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="create the event even if one with the same name exists",
    )
    return parser


def main(argv: list[str] | None = None, *, client: httpx2.Client | None = None) -> int:
    """CLI entry point. ``client`` is a test seam; the CLI builds its own."""
    args = _parser().parse_args(argv)
    token = os.environ.get(API_TOKEN_ENV, "")
    if client is None and not token:
        print(
            f"seed: set {API_TOKEN_ENV} to the server's admin API token",
            file=sys.stderr,
        )
        return 2
    try:
        fixture = load_fixture(args.fixture)
        # Close the client only when this function opened it.
        if client is None:
            opened = httpx2.Client(
                base_url=args.base_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
        else:
            opened = contextlib.nullcontext(client)
        with opened as http:
            event = seed(
                http,
                fixture,
                open_round=args.open_round,
                allow_duplicate=args.allow_duplicate,
            )
    except SeedError as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 1
    # The codes are credentials meant to be displayed: the host prints
    # them as QR codes. They go to stdout only, never to a log.
    print(f"event:     {event['name']} ({event['id']})")
    print(f"status:    {event['status']}")
    print(f"riddles:   {len(fixture['riddles'])}")
    print(f"join code: {event['join_code']}")
    print(f"mod code:  {event['mod_code']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
