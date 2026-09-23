"""Run the built PWA against an isolated, temporary FastAPI instance.

The app talks to a stub OpenID provider (``stub_idp.py``) started on a second
port, so the moderator link can complete its SSO round-trip without a real
issuer. Same host, different port: the Lax transaction cookie survives the
authorize->callback navigation, and the app fetches discovery, JWKS, and the
token over real HTTP, exercising the production OIDC code paths unmodified.
"""

from __future__ import annotations

import argparse
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn

from app import oidc
from app.main import create_app
from app.security import hash_password
from stub_idp import StubIdp


E2E_ADMIN_USERNAME = "browser-test-admin"
E2E_ADMIN_PASSWORD = "browser-test-only"
E2E_OIDC_CLIENT_ID = "arkham-e2e"
E2E_OIDC_CLIENT_SECRET = "arkham-e2e-secret"


def _wait_for(url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"stub OpenID provider did not start: {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--idp-port", type=int, default=4174)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    issuer = f"http://127.0.0.1:{args.idp_port}"
    idp = StubIdp(issuer, E2E_OIDC_CLIENT_ID)
    threading.Thread(
        target=uvicorn.run,
        args=(idp.app,),
        kwargs={"host": "127.0.0.1", "port": args.idp_port, "log_level": "warning"},
        daemon=True,
    ).start()
    _wait_for(f"{issuer}/.well-known/openid-configuration")

    with tempfile.TemporaryDirectory(prefix="arkham-browser-smoke-") as runtime:
        runtime_dir = Path(runtime)
        app = create_app(
            db_path=runtime_dir / "arkham.db",
            admin_config=(E2E_ADMIN_USERNAME, hash_password(E2E_ADMIN_PASSWORD)),
            cookie_secure=False,
            photos_dir=runtime_dir / "photos",
            static_dir=repo_root / "web" / "dist",
            oidc_config=oidc.OidcConfig(
                issuer=issuer,
                client_id=E2E_OIDC_CLIENT_ID,
                client_secret=E2E_OIDC_CLIENT_SECRET,
            ),
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
