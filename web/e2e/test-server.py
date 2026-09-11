"""Run the built PWA against an isolated, temporary FastAPI instance."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import uvicorn

from app.main import create_app
from app.security import hash_password


E2E_ADMIN_USERNAME = "browser-test-admin"
E2E_ADMIN_PASSWORD = "browser-test-only"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="arkham-browser-smoke-") as runtime:
        runtime_dir = Path(runtime)
        app = create_app(
            db_path=runtime_dir / "arkham.db",
            admin_config=(E2E_ADMIN_USERNAME, hash_password(E2E_ADMIN_PASSWORD)),
            cookie_secure=False,
            photos_dir=runtime_dir / "photos",
            static_dir=repo_root / "web" / "dist",
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
