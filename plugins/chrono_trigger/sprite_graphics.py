"""View and safely replace Steam character sprite bitmap graphics.

CTViewer's proven PC backend (``FileSystemBackendPc::get_sprite_graphics`` /
``get_sprite_palette``) reads ``Game/chara/bmp/c<NNN>_<N>.bmp`` directly as a
sprite's pixel data, and treats frame ``_0`` as also supplying the palette
shared by every other frame of that sprite. Those are exactly the resources
this module previews and replaces; it does not invent a new graphics format.

``Game/chara/png/c<NNN>_<N>.png`` files also exist in the archive, but they
are a different, larger (2x) rendering not read by CTViewer's PC backend, so
Lexeditor does not treat them as the game's sprite graphic.
"""
from __future__ import annotations

import base64
import io
import re

from PIL import Image

from .project import OverlayStore, digest


SPRITE_BMP_RE = re.compile(r"^Game/chara/bmp/c(\d{3})_(\d+)\.bmp$", re.IGNORECASE)
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def sprite_bmp_path(sprite_index: int, bitmap_index: int) -> str:
    return f"Game/chara/bmp/c{sprite_index:03d}_{bitmap_index}.bmp"


def sprite_frame_indexes(store: OverlayStore, sprite_index: int) -> list[int]:
    prefix = f"Game/chara/bmp/c{sprite_index:03d}_"
    frames = []
    for path in store.archive.paths(prefix):
        match = SPRITE_BMP_RE.match(path)
        if match and int(match.group(1)) == sprite_index:
            frames.append(int(match.group(2)))
    return sorted(frames)


def _to_png_base64(payload: bytes) -> tuple[str, int, int]:
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        width, height = image.size
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii"), width, height


def load_sprite_image(store: OverlayStore, sprite_index: int, bitmap_index: int, source: str = "mine") -> dict:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    path = sprite_bmp_path(sprite_index, bitmap_index)
    if not store.archive.has(path):
        raise KeyError(f"No sprite graphic at {path}")
    payload, origin = store.read(path, source)
    try:
        png_base64, width, height = _to_png_base64(payload)
    except (OSError, ValueError) as error:
        raise ValueError(f"{path} is not a readable image") from error
    return {
        "path": path, "source": origin, "sha256": digest(payload),
        "width": width, "height": height, "pngBase64": png_base64,
        "frames": sprite_frame_indexes(store, sprite_index),
    }


def save_sprite_image(
    store: OverlayStore, sprite_index: int, bitmap_index: int, expected_sha256: str, image_base64: str
) -> dict:
    path = sprite_bmp_path(sprite_index, bitmap_index)
    if not store.archive.has(path):
        raise KeyError(f"No sprite graphic at {path}")
    current, _ = store.read(path, "mine")
    if digest(current) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    try:
        raw = base64.b64decode(str(image_base64), validate=True)
    except ValueError as error:
        raise ValueError("Replacement image is not valid base64") from error
    if not raw:
        raise ValueError("Replacement image is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Replacement image exceeds the {MAX_UPLOAD_BYTES}-byte limit")
    try:
        with Image.open(io.BytesIO(current)) as original:
            original.load()
            original_size = original.size
            original_mode = original.mode
    except (OSError, ValueError) as error:
        raise ValueError(f"{path} is not a readable image") from error
    try:
        with Image.open(io.BytesIO(raw)) as uploaded:
            uploaded.load()
            if uploaded.size != original_size:
                raise ValueError(
                    f"Replacement image must be exactly {original_size[0]}x{original_size[1]} pixels, "
                    "matching the existing sprite sheet"
                )
            converted = (
                uploaded.convert("P", palette=Image.ADAPTIVE, colors=256)
                if original_mode == "P" else uploaded.convert(original_mode)
            )
            buffer = io.BytesIO()
            converted.save(buffer, format="BMP")
    except (OSError, ValueError) as error:
        raise ValueError("Replacement file is not a readable image") from error
    store.write(path, expected_sha256, buffer.getvalue())
    return load_sprite_image(store, sprite_index, bitmap_index, "mine")
