"""Chrono Trigger Steam fixed 256-color RGB555 palette editing."""
from __future__ import annotations

import re
import struct

from .project import OverlayStore, digest, validate_resource_path


FIELD_PALETTE_RE = re.compile(r"^Game/field/palette_bin/plt(\d+)\.bin$", re.IGNORECASE)
WORLD_PALETTE_RE = re.compile(r"^Game/world/plt_bin/plt(\d+)\.bin$", re.IGNORECASE)
PALETTE_PREFIX = 2
COLOR_COUNT = 256
PALETTE_BYTES = PALETTE_PREFIX + COLOR_COUNT * 2


def palette_files(store: OverlayStore) -> list[dict]:
    rows = []
    for path in store.archive.paths():
        match = FIELD_PALETTE_RE.match(path) or WORLD_PALETTE_RE.match(path)
        if not match:
            continue
        rows.append({
            "path": path,
            "id": int(match.group(1)),
            "kind": "Area" if FIELD_PALETTE_RE.match(path) else "World",
            "label": f"{'Area' if FIELD_PALETTE_RE.match(path) else 'World'} palette {int(match.group(1))}",
        })
    return sorted(rows, key=lambda row: (row["kind"], row["id"], row["path"]))


def _component8(value5: int) -> int:
    return round(value5 * 255 / 31)


def _component5(value8: int) -> int:
    return round(value8 * 31 / 255)


def _decode_color(index: int, raw: int) -> dict:
    red5 = raw & 0x1F
    green5 = (raw >> 5) & 0x1F
    blue5 = (raw >> 10) & 0x1F
    red, green, blue = map(_component8, (red5, green5, blue5))
    return {
        "token": str(index),
        "index": index,
        "hex": f"#{red:02X}{green:02X}{blue:02X}",
        "red5": red5,
        "green5": green5,
        "blue5": blue5,
        "preservedBit15": bool(raw & 0x8000),
    }


def load_palette(store: OverlayStore, path: str, source: str = "mine") -> dict:
    path = validate_resource_path(path)
    if not (FIELD_PALETTE_RE.match(path) or WORLD_PALETTE_RE.match(path)):
        raise ValueError("Only Steam field/world plt*.bin palettes use this editor")
    payload, origin = store.read(path, source)
    if len(payload) < PALETTE_BYTES:
        raise ValueError(f"{path} is shorter than its 2-byte prefix plus 256 RGB555 colors")
    rows = []
    for index in range(COLOR_COUNT):
        raw = struct.unpack_from("<H", payload, PALETTE_PREFIX + index * 2)[0]
        rows.append(_decode_color(index, raw))
    return {
        "path": path, "source": origin, "sha256": digest(payload), "rows": rows,
        "prefixHex": payload[:PALETTE_PREFIX].hex().upper(),
        "trailingBytes": len(payload) - PALETTE_BYTES,
    }


def _parse_hex(value: str) -> tuple[int, int, int]:
    text = str(value).strip()
    if len(text) != 7 or not text.startswith("#"):
        raise ValueError("Palette color must be #RRGGBB")
    try:
        return tuple(int(text[offset:offset + 2], 16) for offset in (1, 3, 5))
    except ValueError as error:
        raise ValueError("Palette color must be #RRGGBB") from error


def save_palette(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    current = load_palette(store, path, "mine")
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256 or current["sha256"] != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    output = bytearray(payload)
    seen = set()
    by_token = {row["token"]: row for row in current["rows"]}
    for edit in edits:
        token = str(edit["token"])
        if token in seen or token not in by_token:
            raise ValueError("Invalid or duplicate palette color edit")
        seen.add(token)
        row = by_token[token]
        red, green, blue = _parse_hex(edit["hex"])
        raw = (0x8000 if row["preservedBit15"] else 0)
        raw |= _component5(red)
        raw |= _component5(green) << 5
        raw |= _component5(blue) << 10
        struct.pack_into("<H", output, PALETTE_PREFIX + row["index"] * 2, raw)
    store.write(path, expected_sha256, bytes(output))
    return load_palette(store, path, "mine")
