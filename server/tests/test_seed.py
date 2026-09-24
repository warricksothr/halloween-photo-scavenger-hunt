"""Demo seeder tests (TKT-01M384GE6JEAN6SN72N4FGCMNA).

The seeder is an HTTP client of the admin API, so these tests hand it a
real ``TestClient`` carrying the bearer token: every call runs the real
route, auth, CSRF middleware, and audit write. Only transport failure and
error bodies the real routes never send are faked, with
``httpx2.MockTransport``.
"""

import copy
import json

import httpx2
import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import create_app
from app.security import hash_password

TOKEN = "seed-test-token-4b1e"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    """A bearer-authenticated client, as the seeder builds it: no cookie,
    no CSRF pair. The token is read at startup, so it is set first."""
    monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", TOKEN)
    app = create_app(
        tmp_path / "seed.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
    )
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client


def _fixture(**overrides):
    data = {
        "name": "Test Demo",
        "leaderboard_visibility": "final-reveal",
        "riddles": [
            {"text": "Second", "sort_order": 2, "hints": ["b1", "b2"]},
            {"text": "First", "sort_order": 1, "hints": ["a1", "a2", "a3"]},
        ],
    }
    data.update(overrides)
    return data


def test_the_bundled_fixture_is_valid_and_uses_the_hint_ladder():
    data = seed.load_fixture(seed.DEFAULT_FIXTURE)
    assert len(data["riddles"]) == 12
    # Round-1 review: every riddle carries several levels, vague first.
    assert all(len(r["hints"]) >= 2 for r in data["riddles"])


def test_seed_creates_opens_and_orders_riddles_and_hints(api):
    event = seed.seed(api, _fixture())
    assert event["status"] == "open"
    assert event["join_code"] and event["mod_code"]
    assert event["leaderboard_visibility"] == "final-reveal"
    riddles = api.get(f"/api/admin/events/{event['id']}/riddles").json()
    assert [r["text"] for r in riddles] == ["First", "Second"]
    assert riddles[0]["hints"] == ["a1", "a2", "a3"]
    assert riddles[1]["hints"] == ["b1", "b2"]


def test_seed_writes_through_the_audited_routes(api):
    event = seed.seed(api, _fixture())
    rows = api.app.state.db.execute(
        "SELECT action FROM audit_event WHERE event_id = ? ORDER BY id",
        (event["id"],),
    ).fetchall()
    assert [r["action"] for r in rows] == [
        "event.created",
        "riddle.created",
        "riddle.created",
        "event.opened",
    ]


def test_no_open_leaves_the_event_in_the_lobby(api):
    event = seed.seed(api, _fixture(), open_round=False)
    assert event["status"] == "lobby"


def test_a_rerun_refuses_a_duplicate_name_unless_allowed(api):
    first = seed.seed(api, _fixture())
    with pytest.raises(seed.SeedError, match=first["id"]):
        seed.seed(api, _fixture())
    second = seed.seed(api, _fixture(), allow_duplicate=True)
    assert second["id"] != first["id"]
    assert len(api.get("/api/admin/events").json()) == 2


def test_a_server_refusal_names_the_route_and_the_error_code(api):
    api.headers["Authorization"] = "Bearer wrong"
    with pytest.raises(seed.SeedError) as info:
        seed.seed(api, _fixture())
    message = str(info.value)
    assert "GET /api/admin/events answered 401" in message
    assert "not_authenticated: Admin login required." in message
    # The default path's first call is the duplicate-check read, so the
    # token note must ride the 401 too, not only the write's csrf_failed.
    assert "did not accept the token in $ARKHAM_ADMIN_API_TOKEN" in message


def test_a_wrong_token_on_the_first_write_names_the_token(api):
    # With --allow-duplicate the first call is a write, and a wrong token
    # fails the CSRF check before auth. The message must point at the
    # token, not at reloading a page.
    api.headers["Authorization"] = "Bearer wrong"
    with pytest.raises(seed.SeedError) as info:
        seed.seed(api, _fixture(), allow_duplicate=True)
    message = str(info.value)
    assert "POST /api/admin/events answered 403 (csrf_failed" in message
    assert "did not accept the token in $ARKHAM_ADMIN_API_TOKEN" in message


def test_a_non_json_error_body_is_reported_raw():
    def handler(request):
        return httpx2.Response(502, text="Bad Gateway from nginx")

    client = httpx2.Client(
        base_url="http://seed.test", transport=httpx2.MockTransport(handler)
    )
    with pytest.raises(seed.SeedError, match="502 \\(Bad Gateway from nginx\\)"):
        seed.seed(client, _fixture())


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        # A route's own flat {"error", "message"}.
        (409, {"error": "nope", "message": "No."}, "409 (nope: No.)"),
        # FastAPI's 422: detail is a list, not the wrapped dict, so raw.
        (422, {"detail": [{"msg": "bad"}]}, '422 ({"detail":[{"msg":"bad"}]})'),
    ],
)
def test_error_bodies_are_unwrapped_or_shown_raw(status, body, expected):
    def handler(request):
        if request.method == "GET":
            return httpx2.Response(200, json=[])
        return httpx2.Response(status, json=body)

    client = httpx2.Client(
        base_url="http://seed.test", transport=httpx2.MockTransport(handler)
    )
    with pytest.raises(seed.SeedError) as info:
        seed.seed(client, _fixture())
    assert str(info.value).endswith(expected)


@pytest.mark.parametrize("fail_on", ["riddles", "open"])
def test_a_failure_after_the_create_names_the_event_and_the_recovery(
    api, monkeypatch, fail_on
):
    # A route failing mid-seed leaves the event behind. The error must name
    # it, and the documented recovery (--allow-duplicate) must then work.
    real_request = api.request
    calls = {"n": 0}

    def flaky(method, url, **kwargs):
        if method == "POST" and url.endswith(fail_on):
            calls["n"] += 1
            if calls["n"] == 2 or fail_on == "open":
                return httpx2.Response(503, text="upstream hiccup")
        return real_request(method, url, **kwargs)

    monkeypatch.setattr(api, "request", flaky)
    with pytest.raises(seed.SeedError) as info:
        seed.seed(api, _fixture())
    partial = api.get("/api/admin/events").json()[0]
    message = str(info.value)
    assert "503 (upstream hiccup)" in message
    assert f"event {partial['id']} was created but not finished" in message
    assert partial["status"] == "lobby"
    with pytest.raises(seed.SeedError, match="already exists"):
        seed.seed(api, _fixture())
    monkeypatch.setattr(api, "request", real_request)
    fresh = seed.seed(api, _fixture(), allow_duplicate=True)
    assert fresh["status"] == "open"
    riddles = api.get(f"/api/admin/events/{fresh['id']}/riddles").json()
    assert len(riddles) == 2


def test_a_transport_failure_becomes_a_seed_error():
    def handler(request):
        raise httpx2.ConnectError("connection refused", request=request)

    client = httpx2.Client(
        base_url="http://seed.test", transport=httpx2.MockTransport(handler)
    )
    with pytest.raises(seed.SeedError, match="GET /api/admin/events failed"):
        seed.seed(client, _fixture())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(riddles=[]), "non-empty 'riddles'"),
        (lambda d: d.pop("riddles"), "non-empty 'riddles'"),
        (lambda d: d.update(name=""), "fixture event is invalid"),
        (lambda d: d.update(colour="red"), "fixture event has unknown keys: colour"),
        (lambda d: d["riddles"].append("text"), "riddle 3 must be a JSON object"),
        (
            # The pre-ladder draft's single key must fail, not vanish.
            lambda d: d["riddles"][0].update(hint="one"),
            "riddle 1 has unknown keys: hint",
        ),
        (
            lambda d: d["riddles"][0].update(hints=["x"] * 6),
            "riddle 1 is invalid",
        ),
        (
            lambda d: d["riddles"][1].update(sort_order=2),
            "riddle 2 repeats sort_order 2",
        ),
    ],
)
def test_a_bad_fixture_fails_before_any_write(api, mutate, message):
    data = copy.deepcopy(_fixture())
    mutate(data)
    with pytest.raises(seed.SeedError, match=message):
        seed.seed(api, data)
    assert api.get("/api/admin/events").json() == []


def test_a_fixture_that_is_not_an_object_is_refused():
    with pytest.raises(seed.SeedError, match="must be a JSON object"):
        seed.validate_fixture([])


def test_load_fixture_reports_unreadable_and_malformed_files(tmp_path):
    with pytest.raises(seed.SeedError, match="cannot read fixture"):
        seed.load_fixture(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(seed.SeedError, match="not valid JSON"):
        seed.load_fixture(bad)


def test_main_prints_the_codes_and_exits_zero(api, tmp_path, capsys):
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(_fixture()))
    assert seed.main(["--fixture", str(path)], client=api) == 0
    out = capsys.readouterr().out
    event = api.get("/api/admin/events").json()[0]
    assert f"({event['id']})" in out
    assert "status:    open" in out
    assert "riddles:   2" in out
    assert "join code: " in out and "mod code:  " in out


def test_main_passes_no_open_and_allow_duplicate_through(api, tmp_path, capsys):
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(_fixture()))
    assert seed.main(["--fixture", str(path), "--no-open"], client=api) == 0
    argv = ["--fixture", str(path), "--no-open", "--allow-duplicate"]
    assert seed.main(argv, client=api) == 0
    events = api.get("/api/admin/events").json()
    assert [e["status"] for e in events] == ["lobby", "lobby"]


def test_main_without_a_token_exits_two(monkeypatch, capsys):
    monkeypatch.delenv("ARKHAM_ADMIN_API_TOKEN", raising=False)
    assert seed.main([]) == 2
    assert "ARKHAM_ADMIN_API_TOKEN" in capsys.readouterr().err


def test_main_reports_an_unreachable_server_and_exits_one(monkeypatch, capsys):
    # The real client path: a closed local port refuses the connection,
    # and the operator gets one line rather than a traceback.
    monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", TOKEN)
    assert seed.main(["--base-url", "http://127.0.0.1:1"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("seed: GET /api/admin/events failed")
    assert TOKEN not in err
