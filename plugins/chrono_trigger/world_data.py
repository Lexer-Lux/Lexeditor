"""Fixed-size Chrono Trigger Steam world-header editing.

CTViewer documents seven active 23-byte PC world headers at 0xFD10 in
Game/common/bankc6.bin. The eighth header is unused. Lexeditor edits only
documented active-header bytes and preserves the rest of bankc6.bin verbatim.
"""
from __future__ import annotations

from .project import OverlayStore, digest


BANK_PATH = "Game/common/bankc6.bin"
HEADER_OFFSET = 0xFD10
HEADER_SIZE = 23
WORLD_COUNT = 7

FIELD_OFFSETS = {
    **{f"layer12Graphics{index}": index for index in range(8)},
    **{f"layer3Graphics{index}": 8 + index for index in range(2)},
    "paletteIndex": 10,
    "paletteAnimationIndex": 11,
    **{f"spriteGraphics{index}": 12 + index for index in range(4)},
    "layer12AssemblyIndex": 16,
    "mapIndex": 17,
    "mapPropertiesIndex": 18,
    "musicPropertiesIndex": 19,
    "layer3AssemblyIndex": 20,
    "exitsIndex": 21,
    "scriptIndex": 22,
}
# CTViewer notes that the PC version ignores byte 11 and uses world index for
# palette animation selection. Keep it visible for evidence, but never rewrite it.
EDITABLE_FIELDS = frozenset(key for key in FIELD_OFFSETS if key != "paletteAnimationIndex")


def _payload(store: OverlayStore, source: str) -> tuple[bytes, str]:
    if source not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    payload, origin = store.read(BANK_PATH, source)
    minimum = HEADER_OFFSET + WORLD_COUNT * HEADER_SIZE
    if len(payload) < minimum:
        raise ValueError(
            f"{BANK_PATH} is shorter than the seven documented Steam world headers "
            f"ending at 0x{minimum:X}"
        )
    return payload, origin


def _decode(index: int, payload: bytes, origin: str) -> dict:
    start = HEADER_OFFSET + index * HEADER_SIZE
    row = {
        "token": str(index),
        "id": index,
        "name": f"World {index}",
        "source": origin,
        "byteOffset": start,
    }
    for key, offset in FIELD_OFFSETS.items():
        row[key] = payload[start + offset]
    return row


def load_worlds(store: OverlayStore, source: str = "mine") -> dict:
    payload, origin = _payload(store, source)
    return {
        "path": BANK_PATH,
        "source": origin,
        "sha256": digest(payload),
        "rows": [_decode(index, payload, origin) for index in range(WORLD_COUNT)],
    }


def _u8(name: str, value) -> int:
    number = int(value)
    if not 0 <= number <= 0xFF:
        raise ValueError(f"{name} must be between 0 and 255")
    return number


def save_worlds(store: OverlayStore, expected_sha256: str, edits: list[dict]) -> dict:
    payload, _ = _payload(store, "mine")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{BANK_PATH} changed since it was opened; reload before saving")
    output = bytearray(payload)
    seen: set[str] = set()
    for edit in edits:
        token = str(edit.get("token", ""))
        if token in seen:
            raise ValueError("Duplicate world header edit")
        seen.add(token)
        try:
            index = int(token)
        except ValueError as error:
            raise ValueError("Invalid world header token") from error
        if not 0 <= index < WORLD_COUNT or token != str(index):
            raise ValueError("Invalid world header token")
        values = edit.get("values")
        if not isinstance(values, dict):
            raise ValueError("World header edit values must be an object")
        unknown = set(values) - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported world header fields: {', '.join(sorted(unknown))}")
        start = HEADER_OFFSET + index * HEADER_SIZE
        for key, value in values.items():
            output[start + FIELD_OFFSETS[key]] = _u8(key, value)
    store.write(BANK_PATH, expected_sha256, bytes(output))
    return load_worlds(store, "mine")
