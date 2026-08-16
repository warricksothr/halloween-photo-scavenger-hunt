"""Evidence upload pipeline (increment 5).

The path of one photo (design.md "Upload pipeline" + "Photo access"):

1. **Validate by magic bytes** — never trust Content-Type (hardening
   checklist). We accept JPEG, PNG, and WebP; anything else is a 415.
2. **Re-encode off the event loop** — Pillow work is blocking CPU, so
   the route hands bytes to ``run_in_threadpool``; doing it inside an
   ``async def`` would stall every player for the duration.
3. **Apply EXIF orientation BEFORE stripping EXIF**
   (``ImageOps.exif_transpose``), or a third of the party's photos come
   out sideways. Stripping happens implicitly: we save a fresh file
   without passing ``exif=``, which also removes GPS data (privacy).
4. **Cap dimensions** — derivatives are max ``MAX_DIMENSION`` px on the
   long edge; originals are quarantined to disk and never served.
5. **Perceptual hash** — average-hash (aHash), stored on the row.
   Cross-team comparison is a plain scan at party scale (spec); the
   collision flag arrives in increment 6.

Size is bounded twice: the route rejects uploads over ``MAX_BYTES``
(413) before any Pillow work, and the pipeline re-checks decompressed
dimensions (``MAX_PIXELS``) so a tiny-but-huge bomb (a 10 KB JPEG that
inflates to 50 000×50 000) is refused without allocating the image.

Result of processing one upload: ``ProcessedPhoto(derivative_bytes,
phash, width, height)``. Writing rows/files is the route's job; this
module is pure bytes-in/bytes-out so it is trivially testable.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

# Caps. Phone photos today run 12+ MP; 1920px is plenty for a party
# screen and keeps derivatives small. MAX_PIXELS guards decompression
# bombs (a valid JPEG can declare absurd dimensions).
MAX_BYTES = 15 * 1024 * 1024   # 15 MB wire cap (route enforces)
MAX_DIMENSION = 1920           # long-edge cap for the derivative
MAX_PIXELS = 50_000_000        # decompressed pixel ceiling

JPEG_QUALITY = 85

_MAGIC = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
}
# WebP: RIFF container with a WEBP fourcc.


class NotAnImageError(Exception):
    """Magic bytes matched nothing we accept → 415."""


class TooManyPixelsError(Exception):
    """Declared dimensions exceed MAX_PIXELS → 413."""


@dataclass
class ProcessedPhoto:
    derivative_bytes: bytes
    phash: str          # 16 hex chars (64-bit aHash)
    width: int          # derivative dimensions (post-transpose, post-cap)
    height: int


def sniff_format(data: bytes) -> str:
    """Return 'JPEG' | 'PNG' | 'WEBP' from magic bytes, or raise."""
    for magic, fmt in _MAGIC.items():
        if data.startswith(magic):
            return fmt
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    raise NotAnImageError()


def average_hash(img: Image.Image) -> str:
    """64-bit average hash as 16 hex chars.

    aHash: downscale to 8×8 luminance, threshold each pixel against the
    mean. Near-duplicates (filters, slight crops, screenshots) land
    within a small Hamming distance — increment 6 compares with a plain
    scan (party scale; no index needed, spec).
    """
    small = img.convert("L").resize((8, 8), Image.LANCZOS)
    pixels = list(small.getdata())
    mean = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= mean else 0)
    return f"{bits:016x}"


def process_upload(data: bytes) -> ProcessedPhoto:
    """Blocking pipeline — call via run_in_threadpool, never in async code."""
    sniff_format(data)  # raises NotAnImageError on anything else
    img = Image.open(io.BytesIO(data))
    declared_pixels = img.width * img.height
    if declared_pixels > MAX_PIXELS:
        raise TooManyPixelsError(
            f"{img.width}x{img.height} exceeds {MAX_PIXELS} pixels"
        )
    img.load()

    # Orientation FIRST: exif_transpose returns the image physically
    # rotated per its EXIF tag; only then is it safe to drop metadata.
    img = ImageOps.exif_transpose(img)

    phash = average_hash(img)

    # Cap the long edge, preserving aspect ratio; no-op when smaller.
    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    # Re-encode as a clean JPEG: no exif= argument means EXIF (incl.
    # GPS) is stripped; every player-visible photo is now the same
    # format regardless of what the phone sent.
    if img.mode != "RGB":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY)
    return ProcessedPhoto(
        derivative_bytes=out.getvalue(),
        phash=phash,
        width=img.width,
        height=img.height,
    )
