"""Evidence pipeline tests (increment 5).

Fixture images are generated in-memory with Pillow — no binary fixtures
in the repo, and each test builds exactly the byte pattern it needs
(valid JPEG, PNG, EXIF-rotated, wrong magic, oversized).
"""

import io
import time

import pytest
from PIL import Image

from app import evidence as evidence_module
from app.images import MAX_BYTES, NotAnImageError, process_upload, sniff_format


def make_jpeg(width=800, height=600, color=(30, 90, 140)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


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
    admin.post(f"/api/admin/events/{event['id']}/riddles",
               json={"text": "Find it", "sort_order": 1})
    admin.post(f"/api/admin/events/{event['id']}/open")
    for name in players:
        resp = client.post(f"/api/join/{event['join_code']}",
                           json={"display_name": name})
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

    def test_phash_is_stable_hex(self):
        # Flat-color images hash identically under aHash (all pixels equal
        # the mean → all bits set) — that's the algorithm, not a bug. Use
        # structured images: the same pattern must hash equal, a different
        # pattern must not.
        def split_image(left_color, right_color):
            img = Image.new("RGB", (200, 200))
            for x in range(200):
                for y in range(200):
                    img.putpixel((x, y),
                                 left_color if x < 100 else right_color)
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
        row = conn.execute("SELECT * FROM evidence_item WHERE id = ?",
                           (item["id"],)).fetchone()
        assert len(row["phash"]) == 16
        audit = conn.execute(
            "SELECT details FROM audit_event"
            " WHERE action = 'evidence.uploaded'").fetchone()
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
        resp = _upload(client, b"definitely not an image" * 4,
                       filename="evil.jpg")
        assert resp.status_code == 415
        assert resp.json()["error"] == "not_an_image"

    def test_oversized_upload_413(self, admin, client):
        _party(admin, client)
        resp = _upload(client, b"\xff\xd8\xff" + b"\x00" * (MAX_BYTES + 8))
        assert resp.status_code == 413

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
        conn.execute("UPDATE evidence_item SET created_at = ?",
                     (int(time.time()) - 1200,))
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
        other = TestClient(client.app)
        other.post(f"/api/join/{join_code}", json={"display_name": "Robin"})
        resp = other.get(photo_url)
        assert resp.status_code == 404  # existence not confirmed
        assert other.get("/api/evidence").json() == []  # own drawer only

    def test_upload_requires_auth(self, client):
        resp = client.post("/api/evidence",
                           files={"photo": ("x.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 401
