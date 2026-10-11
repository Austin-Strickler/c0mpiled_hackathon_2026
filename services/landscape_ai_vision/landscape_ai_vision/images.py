"""Load customer photos, fix orientation, strip metadata, shrink for the API.

Phone photos carry GPS coordinates in their EXIF data. We drop all metadata
before the image leaves this module (customer data, roadmap rule R19).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_EDGE = 1568  # long-edge size the vision API uses without further downscaling
MAX_PHOTOS = 12


def find_photos(paths: list[str | Path], max_photos: int | None = None) -> list[Path]:
    """Expand folders and keep only image files, sorted for stable photo indexes.

    With max_photos, a larger set is thinned to an evenly spaced sample, so a
    walk-around of 20+ shots still covers the whole yard.
    """
    found: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            found.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED))
        elif p.suffix.lower() in SUPPORTED and p.exists():
            found.append(p)
    if not found:
        raise FileNotFoundError("No photos found. Supported: " + ", ".join(sorted(SUPPORTED)))
    if max_photos and len(found) > max_photos:
        step = len(found) / max_photos
        found = [found[int(i * step)] for i in range(max_photos)]
    if len(found) > MAX_PHOTOS:
        raise ValueError(f"{len(found)} photos given; the limit is {MAX_PHOTOS} per property. Use --max-photos.")
    return found


def _open(path: Path) -> Image.Image:
    if path.suffix.lower() == ".heic":
        try:
            from pillow_heif import register_heif_opener  # optional dependency

            register_heif_opener()
        except ImportError as e:
            raise RuntimeError("HEIC photo: run `pip install pillow-heif` or convert to JPEG") from e
    return Image.open(path)


def prepare(path: Path, max_edge: int = MAX_EDGE) -> tuple[bytes, tuple[int, int]]:
    """Return clean JPEG bytes (rotated upright, resized, no EXIF) and the new size."""
    with _open(path) as im:
        im = ImageOps.exif_transpose(im)  # phones store rotation in EXIF
        im = im.convert("RGB")  # also discards alpha and metadata
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)  # no exif= argument -> no metadata
        return buf.getvalue(), im.size


def to_api_block(jpeg: bytes) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(jpeg).decode("ascii"),
        },
    }
