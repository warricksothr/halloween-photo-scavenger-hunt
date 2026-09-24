"""The stream follows the role a tab shows (TKT-01M394KVSC6GCC1EDW4NSXZRW3).

A browser can hold a player session and a moderator session at once — the
host who also plays — and each tab shows one of them. ``?as=`` names the
role, so each tab subscribes to its own stream.
"""

import asyncio

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from support import sign_in_moderator
from test_mod import _party

from app.sse import events_stream


def _request(app, cookies):
    cookie = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/events/stream",
            "raw_path": b"/api/events/stream",
            "query_string": b"",
            "headers": [(b"cookie", cookie.encode())],
            "client": ("test", 1234),
            "server": ("test", 80),
            "app": app,
        }
    )


def _subscribe(app, cookies, as_):
    """Run the route once and return the role it subscribed, or the 401."""
    broker = app.state.sse_broker
    before = set(broker._subscribers)
    response = asyncio.run(events_stream(_request(app, cookies), as_=as_))
    if isinstance(response, JSONResponse):
        return response.status_code
    assert isinstance(response, StreamingResponse)
    (sub,) = set(broker._subscribers) - before
    broker.unsubscribe(sub)
    return sub.role


@pytest.fixture()
def both(admin, client):
    """The player ``client`` also joined the event as a moderator."""
    p = _party(admin, client)
    sign_in_moderator(client, subject="host-plays", name="Host", role="admin")
    assert client.post(f"/api/mod/join/{p['mod_code']}").status_code == 201
    return dict(client.cookies.items())


@pytest.mark.parametrize(
    ("as_", "role"),
    [("player", "player"), ("moderator", "moderator"), (None, "moderator")],
)
def test_as_picks_the_session_when_both_are_held(client, both, as_, role):
    # Without ``as`` the moderator cookie still wins, as before this change.
    assert _subscribe(client.app, both, as_) == role


def test_as_names_a_role_the_browser_does_not_hold(admin, client):
    p = _party(admin, client)
    player_only = {
        name: value for name, value in client.cookies.items() if name != "arkham_mod"
    }
    assert p["player_id"]
    assert _subscribe(client.app, player_only, "moderator") == 401
    assert _subscribe(client.app, player_only, "player") == "player"


def test_an_unknown_role_is_a_validation_error(client):
    resp = client.get("/api/events/stream?as=admin")
    assert resp.status_code == 422
