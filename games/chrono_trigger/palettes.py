"""Fixed-size BGR555 palette editors for Chrono Trigger Steam.

CTViewer's PC backend reads both scene and overworld ``plt*.bin`` resources by
skipping a two-byte header and decoding exactly 256 little-endian SNES BGR555
colors. Lexeditor changes individual color words in a loose project overlay;
file size and the two-byte header are always preserved.
"""

from __future__ import annotations

import struct

from .data import OverlayStore, sha256


PALETTE_HEADER_SIZE = 2
PALETTE_COLOR_COUNT = 256
PALETTE_DATA_BYTES = PALETTE_COLOR_COUNT * 2


def palette_path(kind: str, palette_id: int) -> str:
    palette_id = int(palette_id)
    if not 0 <= palette_id <= 0xFFFF:
        raise ValueError("Palette ID must be between 0 and 65535")
    kind = str(kind).casefold()
    if kind == "scene":
        return f"Game/field/palette_bin/plt{palette_id}.bin"
    if kind == "world":
        return f"Game/world/plt_bin/plt{palette_id}.bin"
    raise ValueError("Palette kind must be 'scene' or 'world'")


def decode_bgr555(value: int) -> tuple[int, int, int]:
    value = int(value) & 0x7FFF
    return (
        round((value & 0x1F) * 255 / 31),
        round(((value >> 5) & 0x1F) * 255 / 31),
        round(((value >> 10) & 0x1F) * 255 / 31),
    )


def encode_bgr555(red: int, green: int, blue: int) -> int:
    values = []
    for value, label in ((red, "Red"), (green, "Green"), (blue, "Blue")):
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label} must be an integer") from error
        if not 0 <= number <= 255:
            raise ValueError(f"{label} must be between 0 and 255")
        values.append(round(number * 31 / 255))
    r, g, b = values
    return r | (g << 5) | (b << 10)


def _validate(raw: bytes, path: str) -> None:
    minimum = PALETTE_HEADER_SIZE + PALETTE_DATA_BYTES
    if len(raw) < minimum:
        raise ValueError(f"Chrono Trigger palette is truncated: {path} ({len(raw)} bytes; need {minimum})")


def _color(raw: bytes, index: int) -> dict:
    index = int(index)
    if not 0 <= index < PALETTE_COLOR_COUNT:
        raise ValueError(f"Palette color index must be between 0 and {PALETTE_COLOR_COUNT - 1}")
    offset = PALETTE_HEADER_SIZE + index * 2
    stored = struct.unpack_from("<H", raw, offset)[0]
    value = stored & 0x7FFF
    r, g, b = decode_bgr555(value)
    return {
        "id": index,
        "offset": offset,
        "stored": stored,
        "raw": value,
        "highBit": bool(stored & 0x8000),
        "red": r,
        "green": g,
        "blue": b,
        "hex": f"#{r:02X}{g:02X}{b:02X}",
    }


def load_palette(store: OverlayStore, kind: str, palette_id: int,
                 source: str = "mine") -> dict:
    path = palette_path(kind, palette_id)
    raw, origin = store.read(path, source)
    _validate(raw, path)
    return {
        "kind": "palette",
        "paletteKind": str(kind).casefold(),
        "paletteId": int(palette_id),
        "path": path,
        "source": origin,
        "readOnly": source == "vanilla",
        "sha256": sha256(raw),
        "headerHex": raw[:2].hex(" ").upper(),
        "fileSize": len(raw),
        "colorCount": PALETTE_COLOR_COUNT,
        "trailingBytes": max(0, len(raw) - (PALETTE_HEADER_SIZE + PALETTE_DATA_BYTES)),
        "colors": [_color(raw, index) for index in range(PALETTE_COLOR_COUNT)],
    }


def save_palette_color(store: OverlayStore, kind: str, palette_id: int, color_index: int,
                       expected_sha256: str, values: dict) -> dict:
    """Change one color while preserving header, high bit and every other byte."""
    if not isinstance(values, dict) or not values:
        raise ValueError("Palette color changes must contain raw or RGB values")
    path = palette_path(kind, palette_id)
    raw, _origin = store.read(path, "mine")
    _validate(raw, path)
    if sha256(raw) != str(expected_sha256):
        raise RuntimeError("The palette changed since it was opened; reload before saving")
    index = int(color_index)
    current = _color(raw, index)
    allowed = {"raw", "red", "green", "blue"}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown palette fields: {', '.join(sorted(unknown))}")
    if "raw" in values and any(key in values for key in ("red", "green", "blue")):
        raise ValueError("Specify either raw BGR555 or RGB components, not both")
    if "raw" in values:
        value = int(values["raw"])
        if not 0 <= value <= 0x7FFF:
            raise ValueError("Raw BGR555 value must be between 0 and 32767")
    else:
        red = values.get("red", current["red"])
        green = values.get("green", current["green"])
        blue = values.get("blue", current["blue"])
        value = encode_bgr555(red, green, blue)

    output = bytearray(raw)
    offset = PALETTE_HEADER_SIZE + index * 2
    # The PC reader treats bit 15 as outside the 15-bit color value. Preserve
    # it if present instead of silently normalizing unknown source data.
    stored = value | (current["stored"] & 0x8000)
    struct.pack_into("<H", output, offset, stored)
    if len(output) != len(raw):
        raise AssertionError("Palette edit unexpectedly changed file size")
    store.write(path, bytes(output))
    result = load_palette(store, kind, palette_id, "mine")
    result["savedColor"] = result["colors"][index]
    return result
