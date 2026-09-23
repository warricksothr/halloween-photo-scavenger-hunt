"""Test helpers shared across the suite.

CSRF: a real browser holds the ``arkham_csrf`` cookie (planted by a safe
GET) and echoes the token in a header. Tests that are not about CSRF need
the same pair so they exercise the route rather than the gate. The token
is minted straight from the app's signing key, which also works for the
async clients the concurrency tests build from a bare ASGITransport
(those have no ``.app``). The planting-on-safe-response path is exercised
in test_csrf.py.
"""

from __future__ import annotations

import time

from app import csrf, oidc
from app.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def arm_csrf(client, app=None):
    """Set the matching cookie+header pair on any httpx client."""
    if app is None:
        app = client.app
    token = csrf.issue_token(app.state.csrf_secret)
    client.cookies.set(CSRF_COOKIE_NAME, token)
    client.headers[CSRF_HEADER_NAME] = token
    return client


def sign_in_moderator(
    client, *, subject="user-1", name="Ada Lovelace", email=None, role="moderator"
):
    """Plant a verified OIDC identity on ``client``, as the callback would.

    The moderator routes read ``app.state.oidc_identities`` through the
    ``arkham_oidc`` cookie, so a test can act as a signed-in moderator
    without standing up an identity provider. Returns the identity token.
    """
    token = f"test-identity-{subject}"
    client.app.state.oidc_identities[token] = oidc.OidcIdentity(
        subject=subject,
        name=name,
        email=email,
        role=role,
        expires_at=int(time.time()) + 3600,
    )
    client.cookies.set(oidc.OIDC_COOKIE_NAME, token)
    return token
