"""ID and code generation.

Two kinds of identifiers, per docs/impl/schema.md conventions:

- **Row ids**: ``secrets.token_hex(16)`` — opaque, URL-safe TEXT,
  immune to guess-the-next-integer enumeration.
- **Join/mod codes**: short human-and-QR-facing strings from an
  unambiguous alphabet (no 0/O, 1/I/L) — they get read aloud and typed
  from a projected QR fallback. Stored plaintext by design: they are
  bearer credentials meant to be displayed.
"""

from __future__ import annotations

import secrets

_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_id() -> str:
    return secrets.token_hex(16)


def new_code(length: int = 10) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
