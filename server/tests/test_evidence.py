"""Evidence pipeline tests (increment 5).

Fixture images are generated in-memory with Pillow — no binary fixtures
in the repo, and each test builds exactly the byte pattern it needs
(valid JPEG, PNG, EXIF-rotated, wrong magic, oversized).
"""

import io
import threading
import time

import pytest
from PIL import Image
from support import arm_csrf

from app import evidence as evidence_module
from app import storage
from app.images import (
    MAX_BYTES,
    MAX_DERIVATIVE_BYTES,
    NotAnImageError,
    TooManyPixelsError,
    process_upload,
    sniff_format,
)


def make_jpeg(width=800, height=600, color=(30, 90, 140)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_declared_size_jpeg(width, height) -> bytes:
    """A real JPEG whose SOF0 header declares ``width``×``height``.

    The bytes are tiny; only the declared dimensions are a lie. That is
    the decompression-bomb shape — Pillow reads the size from the header
    before it reads a single pixel."""
    data = bytearray(make_jpeg(8, 8))
    sof0 = data.index(b"\xff\xc0")  # SOF0: length, precision, height, width
    data[sof0 + 5 : sof0 + 7] = height.to_bytes(2, "big")
    data[sof0 + 7 : sof0 + 9] = width.to_bytes(2, "big")
    return bytes(data)


def make_exif_rotated(width=400, height=200) -> bytes:
    """A 400x200 image tagged EXIF orientation 6 (rotate 90° CW on
    display). The correct derivative is 200x400 — sideways if the
    pipeline strips EXIF before applying orientation."""
    img = Image.new("RGB", (width, height), (140, 30, 60))
    exif = Image.Exif()
    exif[274] = 6  # 274 = Orientation tag; 6 = rotate 90 CW
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _party(admin, client, players=("Batman",)):
    """Open event + one player joined; returns (event_id, join_code)."""
    resp = admin.post("/api/admin/events", json={"name": "Photo Party"})
    event = resp.json()
    admin.post(
        f"/api/admin/events/{event['id']}/riddles",
        json={"text": "Find it", "sort_order": 1},
    )
    admin.post(f"/api/admin/events/{event['id']}/open")
    for name in players:
        resp = client.post(
            f"/api/join/{event['join_code']}", json={"display_name": name}
        )
        assert resp.status_code == 201, resp.text
    return event["id"], event["join_code"]


def _upload(client, data, riddle_id=None, filename="shot.jpg"):
    params = {}
    if riddle_id is not None:
        params["riddle_id"] = riddle_id
    return client.post(
        "/api/evidence",
        files={"photo": (filename, data, "image/jpeg")},
        params=params,
    )


class TestPipelineUnit:
    def test_magic_bytes_accepted_and_rejected(self):
        assert sniff_format(make_jpeg()) == "JPEG"
        png = io.BytesIO()
        Image.new("RGB", (10, 10)).save(png, format="PNG")
        assert sniff_format(png.getvalue()) == "PNG"
        with pytest.raises(NotAnImageError):
            sniff_format(b"GIF89a not actually but close enough")
        with pytest.raises(NotAnImageError):
            sniff_format(b"\x00" * 32)

    def test_reencode_strips_exif_and_caps_dimensions(self):
        big = make_jpeg(4000, 3000)
        result = process_upload(big)
        assert max(result.width, result.height) <= 1920
        img = Image.open(io.BytesIO(result.derivative_bytes))
        assert img.format == "JPEG"
        assert not img.getexif()  # EXIF gone, GPS with it

    def test_orientation_applied_before_strip(self):
        result = process_upload(make_exif_rotated(400, 200))
        # Rotated for display: 400x200 tagged rotate-90 becomes 200x400.
        assert (result.width, result.height) == (200, 400)

    def test_garbage_after_magic_is_not_an_image(self):
        # Magic bytes match, the rest is nonsense: Pillow raises
        # UnidentifiedImageError, which must not reach the route as a 500.
        with pytest.raises(NotAnImageError):
            process_upload(b"\xff\xd8\xff" + b"garbage" * 16)

    def test_truncated_jpeg_is_not_an_image(self):
        raw = make_jpeg(800, 600)
        with pytest.raises(NotAnImageError):
            process_upload(raw[: len(raw) // 3])

    def test_decompression_bomb_is_too_many_pixels(self):
        # Declared size is past twice Pillow's own ceiling, so Pillow
        # refuses during open.
        with pytest.raises(TooManyPixelsError):
            process_upload(make_declared_size_jpeg(20000, 20000))

    def test_decompression_bomb_warning_is_too_many_pixels(self):
        # Between Pillow's ceiling and twice it, Pillow warns instead of
        # raising; pytest's filterwarnings = ["error"] promotes that to an
        # exception, so this is the branch that catches the warning.
        with pytest.raises(TooManyPixelsError):
            process_upload(make_declared_size_jpeg(10000, 10000))

    def test_declared_pixels_over_cap_is_too_many_pixels(self):
        # Declared size is under Pillow's ceiling, so this is our own
        # MAX_PIXELS check doing the refusing.
        with pytest.raises(TooManyPixelsError):
            process_upload(make_declared_size_jpeg(8000, 8000))

    def test_derivative_failure_is_not_blamed_on_the_upload(self, monkeypatch):
        # Only the decode is translated. A fault while building the
        # derivative is the server's, so it must surface as an OSError
        # (a 500), not be re-labelled NotAnImageError (a 415).
        def boom(_img):
            raise OSError("encoder exploded")

        monkeypatch.setattr("app.images.average_hash", boom)
        with pytest.raises(OSError):
            process_upload(make_jpeg())

    def test_phash_is_stable_hex(self):
        # Flat-color images hash identically under aHash (all pixels equal
        # the mean → all bits set) — that's the algorithm, not a bug. Use
        # structured images: the same pattern must hash equal, a different
        # pattern must not.
        def split_image(left_color, right_color):
            img = Image.new("RGB", (200, 200))
            for x in range(200):
                for y in range(200):
                    img.putpixel((x, y), left_color if x < 100 else right_color)
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            return buf.getvalue()

        a = process_upload(split_image((220, 30, 30), (30, 30, 220)))
        b = process_upload(split_image((220, 30, 30), (30, 30, 220)))
        assert a.phash == b.phash
        assert len(a.phash) == 16
        c = process_upload(split_image((30, 220, 30), (220, 220, 30)))
        assert c.phash != a.phash


class TestUploadEndpoint:
    def test_upload_round_trip(self, admin, client):
        _party(admin, client)
        resp = _upload(client, make_jpeg())
        assert resp.status_code == 201, resp.text
        item = resp.json()
        assert item["photo_url"].endswith("/photo")

        drawer = client.get("/api/evidence").json()
        assert len(drawer) == 1
        assert drawer[0]["id"] == item["id"]

        photo = client.get(item["photo_url"])
        assert photo.status_code == 200
        assert photo.headers["content-type"] == "image/jpeg"
        assert photo.content.startswith(b"\xff\xd8\xff")

        # Row carries the phash; the audit row rides the same transaction.
        conn = client.app.state.db
        row = conn.execute(
            "SELECT * FROM evidence_item WHERE id = ?", (item["id"],)
        ).fetchone()
        assert len(row["phash"]) == 16
        audit = conn.execute(
            "SELECT details FROM audit_event WHERE action = 'evidence.uploaded'"
        ).fetchone()
        import json

        assert json.loads(audit[0])["phash"] == row["phash"]

    def test_riddle_tag(self, admin, client):
        event_id, _ = _party(admin, client)
        riddle = admin.get(f"/api/admin/events/{event_id}/riddles").json()[0]
        resp = _upload(client, make_jpeg(), riddle_id=riddle["id"])
        assert resp.status_code == 201
        assert resp.json()["riddle_id"] == riddle["id"]
        # A riddle from another event (or invented) is 404.
        resp = _upload(client, make_jpeg(), riddle_id="no-such-riddle")
        assert resp.status_code == 404

    def test_wrong_magic_bytes_415(self, admin, client):
        _party(admin, client)
        resp = _upload(client, b"definitely not an image" * 4, filename="evil.jpg")
        assert resp.status_code == 415
        assert resp.json()["error"] == "not_an_image"

    def test_oversized_upload_413(self, admin, client):
        _party(admin, client)
        resp = _upload(client, b"\xff\xd8\xff" + b"\x00" * (MAX_BYTES + 8))
        assert resp.status_code == 413

    def test_malformed_image_is_415_not_500(self, admin, client):
        # Magic bytes are right but nothing decodes: a header-only file
        # and a truncated real one. Both are the client's bad bytes, so
        # 415 — not a server fault.
        _party(admin, client)
        raw = make_jpeg(800, 600)
        for data in (b"\xff\xd8\xff" + b"garbage" * 16, raw[: len(raw) // 3]):
            resp = _upload(client, data, filename="broken.jpg")
            assert resp.status_code == 415, resp.text
            assert resp.json()["error"] == "not_an_image"

    def test_decompression_bomb_is_413_not_500(self, admin, client):
        # A few hundred bytes that claim 20000×20000 pixels.
        _party(admin, client)
        resp = _upload(client, make_declared_size_jpeg(20000, 20000))
        assert resp.status_code == 413, resp.text
        assert resp.json()["error"] == "too_large"

    def test_rate_limit_429(self, admin, client, monkeypatch):
        _party(admin, client)
        # Lower the limit rather than uploading 30 images.
        monkeypatch.setattr(evidence_module, "RATE_LIMIT_UPLOADS", 2)
        assert _upload(client, make_jpeg()).status_code == 201
        assert _upload(client, make_jpeg()).status_code == 201
        resp = _upload(client, make_jpeg())
        assert resp.status_code == 429
        assert resp.json()["error"] == "rate_limited"

        # The window is rolling: backdate the two uploads beyond it and
        # the next upload succeeds.
        conn = client.app.state.db
        conn.execute(
            "UPDATE evidence_item SET created_at = ?", (int(time.time()) - 1200,)
        )
        conn.commit()
        assert _upload(client, make_jpeg()).status_code == 201

    def test_other_team_gets_404_not_403(self, admin, client):
        # Two players (two teams-of-one). Upload as the first, attempt
        # to read as the second.
        _, join_code = _party(admin, client, players=("Batman",))
        resp = _upload(client, make_jpeg())
        photo_url = resp.json()["photo_url"]
        # Second player: fresh cookie jar via a new client on the same app.
        from fastapi.testclient import TestClient

        other = arm_csrf(TestClient(client.app))
        other.post(f"/api/join/{join_code}", json={"display_name": "Robin"})
        resp = other.get(photo_url)
        assert resp.status_code == 404  # existence not confirmed
        assert other.get("/api/evidence").json() == []  # own drawer only

    def test_upload_requires_auth(self, client):
        resp = client.post(
            "/api/evidence", files={"photo": ("x.jpg", make_jpeg(), "image/jpeg")}
        )
        assert resp.status_code == 401


class TestDiskGuardrail:
    def test_low_disk_rejects_before_any_work(self, admin, client, monkeypatch):
        _party(admin, client)
        # Let the middleware's check (declared body only) pass so the
        # route's own guard — the one that also accounts for the
        # derivative — is the branch under test.
        monkeypatch.setattr(
            storage,
            "has_room",
            lambda path, extra_bytes, minimum: extra_bytes < MAX_DERIVATIVE_BYTES,
        )

        resp = _upload(client, make_jpeg())
        assert resp.status_code == 507, resp.text
        assert resp.json()["error"] == "storage_full"
        # Refused before Pillow, the row, and the files: nothing to undo.
        conn = client.app.state.db
        assert conn.execute("SELECT COUNT(*) FROM evidence_item").fetchone()[0] == 0
        assert list(client.app.state.photos_dir.rglob("*")) == []

    def test_room_available_uploads_normally(self, admin, client, monkeypatch):
        _party(admin, client)
        calls = []
        real = storage.has_room

        def spy(path, extra_bytes, minimum):
            calls.append((extra_bytes, minimum))
            return real(path, extra_bytes, minimum)

        monkeypatch.setattr(storage, "has_room", spy)
        assert _upload(client, make_jpeg()).status_code == 201
        # The guardrail was consulted, not skipped on the happy path, and
        # the route's check accounts for the derivative as well as the body
        # (the middleware's earlier check only sees the declared length).
        assert calls and calls[0][1] == client.app.state.min_free_bytes
        assert any(extra >= MAX_DERIVATIVE_BYTES for extra, _ in calls)


class TestOffTheEventLoop:
    """The upload route is ``async def`` (it awaits the body), so any
    blocking call left in it would stall every player. The DB and file
    half runs in the threadpool instead (RFWQM9)."""

    def test_upload_stores_off_the_event_loop(self, admin, client, monkeypatch):
        _party(admin, client)
        names = []
        real = storage.has_room

        def spy(path, extra_bytes, minimum):
            names.append(threading.current_thread().name)
            return real(path, extra_bytes, minimum)

        monkeypatch.setattr(storage, "has_room", spy)
        assert _upload(client, make_jpeg()).status_code == 201
        # The middleware's check runs on the loop; the route's own check
        # lives in _store_upload, which must be a threadpool hop.
        assert any("worker" in name.lower() for name in names), names
