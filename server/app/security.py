"""Password hashing, isolated so modules that only need session plumbing
(auth.py) don't import argon2 directly.

argon2id is the spec's choice (design.md hardening checklist: "real
password hashing (argon2id)"). The admin password hash is generated
offline and provided via config; there is no set-password flow in the
app itself.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Generate the config value for ARKHAM_ADMIN_PASSWORD_HASH:
    ``python -m app.security '<password>'`` prints one."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-cost check: argon2id runs regardless of outcome so
    timing does not leak information about the hash."""
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError):
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.security '<password>'")
    print(hash_password(sys.argv[1]))
