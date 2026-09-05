"""Strict FF8 PC field-background tile codec and renderer.

The byte layout and render addressing follow Deling's GPLv3
``BackgroundFile`` implementation.  Lexeditor patches only the fields that
Deling exposes.  It keeps packed, reserved, terminator, and MIM bytes intact.
"""

from __future__ import annotations

from io import BytesIO
import struct

from PIL import Image


OLD_MIM_SIZE = 401_408
NEW_MIM_SIZE = 438_272
TILE_SIZE = 16
OLD_SHORT_TILE_SIZE = 14
TERMINATOR_X = 0x7FFF
MAX_RENDER_COORDINATE = 999

_COMMON_FIELDS = (
    "x", "y", "z", "sourceX", "sourceY", "texture", "palette",
    "blend", "draw", "depth",
)
_NEW_FIELDS = _COMMON_FIELDS + ("layer", "blendType", "parameter", "state")
_OLD_FIELDS = _COMMON_FIELDS + ("parameter", "state")
_OLD_SHORT_FIELDS = _COMMON_FIELDS


def editable_fields(variant: str) -> tuple[str, ...]:
    try:
        return {"new": _NEW_FIELDS, "old": _OLD_FIELDS,
                "old-short": _OLD_SHORT_FIELDS}[variant]
    except KeyError as error:
        raise ValueError(f"Unknown field MAP variant: {variant}") from error


def _stride(map_data: bytes) -> int:
    """Apply Deling's final 0x7fff-record rule without accepting trailing data."""
    candidates = []
    for size in (TILE_SIZE, OLD_SHORT_TILE_SIZE):
        if len(map_data) >= size and len(map_data) % size == 0:
            if struct.unpack_from("<h", map_data, len(map_data) - size)[0] == TERMINATOR_X:
                candidates.append(size)
    if len(candidates) != 1:
        raise ValueError("Field MAP needs one final 14-byte or 16-byte terminator record")
    return candidates[0]


def _variant(map_data: bytes, mim_data: bytes, stride: int) -> str:
    if len(mim_data) == OLD_MIM_SIZE:
        return "old-short" if stride == OLD_SHORT_TILE_SIZE else "old"
    if len(mim_data) != NEW_MIM_SIZE:
        raise ValueError(
            f"Field MIM has {len(mim_data)} bytes; expected {OLD_MIM_SIZE} or {NEW_MIM_SIZE}"
        )
    if stride != TILE_SIZE:
        raise ValueError("A new-format field background cannot use 14-byte tiles")
    # This is Deling's documented PC fallback for early maps stored in a
    # new-size MIM container.  In the old layout byte 12 is parameter data.
    for offset in range(0, len(map_data) - stride, stride):
        if map_data[offset + 13] >= 60:  # Tile2::blendType
            return "old"
    return "new"


def _decode_tile(data: bytes, offset: int, tile_id: int, variant: str) -> dict:
    if variant == "new":
        x, y, z, texture_word, palette_word, source_x, source_y, layer, \
            blend_type, parameter, state = struct.unpack_from("<hhHHHBBBBBB", data, offset)
    else:
        x, y, source_x, source_y, z, texture_word, palette_word = struct.unpack_from(
            "<hhHHHHH", data, offset
        )
        if variant == "old":
            parameter, state = struct.unpack_from("<BB", data, offset + 14)
        else:
            parameter, state = 255, 0
        layer = 0
        blend = (texture_word >> 5) & 3
        blend_type = 1 if blend & 1 else 4
    return {
        "id": tile_id,
        "offset": offset,
        "x": x,
        "y": y,
        "z": z,
        "sourceX": source_x,
        "sourceY": source_y,
        "texture": texture_word & 0xF,
        "draw": bool((texture_word >> 4) & 1),
        "blend": (texture_word >> 5) & 3,
        "depth": (texture_word >> 7) & 3,
        "palette": (palette_word >> 6) & 0xF,
        "layer": layer,
        "blendType": blend_type,
        "parameter": parameter,
        "state": state,
    }


def read(map_data: bytes, mim_data: bytes) -> dict:
    """Decode all MAP tiles and the filter metadata needed by the preview."""
    stride = _stride(map_data)
    variant = _variant(map_data, mim_data, stride)
    tile_count = len(map_data) // stride - 1
    if tile_count < 0 or tile_count > 100_000:
        raise ValueError("Field MAP tile count is unsafe")
    tiles = []
    for tile_id in range(tile_count):
        offset = tile_id * stride
        tile = _decode_tile(map_data, offset, tile_id, variant)
        if tile["x"] == TERMINATOR_X:
            raise ValueError("Field MAP contains a terminator before its final record")
        tiles.append(tile)
    terminator_offset = tile_count * stride
    if struct.unpack_from("<h", map_data, terminator_offset)[0] != TERMINATOR_X:
        raise ValueError("Field MAP terminator is missing")
    parameters = sorted({(tile["parameter"], tile["state"]) for tile in tiles
                         if tile["parameter"] != 255})
    layers = sorted({tile["layer"] for tile in tiles})
    bounded = [tile for tile in tiles
               if abs(tile["x"]) <= MAX_RENDER_COORDINATE and
               abs(tile["y"]) <= MAX_RENDER_COORDINATE]
    if tiles and not bounded:
        raise ValueError("Field MAP has no tiles within Deling's render bounds")
    bounds = {
        "left": max((-tile["x"] for tile in bounded if tile["x"] < 0), default=0),
        "right": max((tile["x"] for tile in bounded if tile["x"] >= 0), default=0),
        "top": max((-tile["y"] for tile in bounded if tile["y"] < 0), default=0),
        "bottom": max((tile["y"] for tile in bounded if tile["y"] >= 0), default=0),
    }
    return {
        "variant": variant,
        "tileSize": stride,
        "tileCount": tile_count,
        "tiles": tiles,
        "layers": layers,
        "parameterStates": [{"parameter": parameter, "state": state}
                            for parameter, state in parameters],
        "bounds": bounds,
    }


def _field_limits(variant: str, field: str) -> tuple[int, int] | None:
    limits = {
        "x": (-32768, 32767), "y": (-32768, 32767), "z": (0, 65535),
        "sourceX": (0, 255), "sourceY": (0, 255), "texture": (0, 15),
        "palette": (0, 15), "blend": (0, 3), "depth": (0, 3),
        "layer": (0, 255), "blendType": (0, 4),
        "parameter": (0, 255), "state": (0, 255),
    }
    allowed = (_NEW_FIELDS if variant == "new" else
               _OLD_FIELDS if variant == "old" else _OLD_SHORT_FIELDS)
    return limits[field] if field in allowed and field != "draw" else None


def _write_field(output: bytearray, tile: dict, variant: str, field: str,
                 value: object) -> bool:
    offset = tile["offset"]
    if field == "draw":
        if field not in (_NEW_FIELDS if variant == "new" else _COMMON_FIELDS):
            raise ValueError("Draw is not available in this MAP variant")
        if type(value) is not bool:
            raise ValueError("Field background draw must be a boolean")
        word_offset = offset + (6 if variant == "new" else 10)
        word = struct.unpack_from("<H", output, word_offset)[0]
        word = (word | 0x10) if value else (word & ~0x10)
        struct.pack_into("<H", output, word_offset, word)
        return tile[field] != value
    limit = _field_limits(variant, field)
    if limit is None:
        raise ValueError(f"Field background {field} is not editable in {variant} MAP tiles")
    if isinstance(value, bool):
        raise ValueError(f"Field background {field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Field background {field} must be an integer") from error
    if number != value or not limit[0] <= number <= limit[1]:
        raise ValueError(f"Field background {field} must be {limit[0]} to {limit[1]}")
    if field in {"x", "y"}:
        struct.pack_into("<h", output, offset + (0 if field == "x" else 2), number)
    elif field == "z":
        struct.pack_into("<H", output, offset + (4 if variant == "new" else 8), number)
    elif field in {"sourceX", "sourceY"}:
        position = offset + ((10 if field == "sourceX" else 11) if variant == "new"
                             else (4 if field == "sourceX" else 6))
        struct.pack_into("<B" if variant == "new" else "<H", output, position, number)
    elif field in {"texture", "blend", "depth"}:
        word_offset = offset + (6 if variant == "new" else 10)
        word = struct.unpack_from("<H", output, word_offset)[0]
        mask, shift = {"texture": (0xF, 0), "blend": (0x3, 5), "depth": (0x3, 7)}[field]
        word = (word & ~(mask << shift)) | ((number & mask) << shift)
        struct.pack_into("<H", output, word_offset, word)
    elif field == "palette":
        word_offset = offset + (8 if variant == "new" else 12)
        word = struct.unpack_from("<H", output, word_offset)[0]
        struct.pack_into("<H", output, word_offset,
                         (word & ~(0xF << 6)) | ((number & 0xF) << 6))
    else:
        positions = ({"layer": 12, "blendType": 13, "parameter": 14, "state": 15}
                     if variant == "new" else {"parameter": 14, "state": 15})
        struct.pack_into("<B", output, offset + positions[field], number)
    return tile[field] != number


def apply_edits(map_data: bytes, mim_data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Patch Deling-exposed tile fields in the original MAP byte buffer."""
    parsed = read(map_data, mim_data)
    output = bytearray(map_data)
    changed = 0
    seen: set[tuple[int, str]] = set()
    allowed = {"tile", *_NEW_FIELDS}
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) - allowed or "tile" not in edit:
            raise ValueError("Field background edit has unsupported fields or no tile ID")
        tile_id = int(edit["tile"])
        if not 0 <= tile_id < parsed["tileCount"]:
            raise ValueError("Field background edit identifies an invalid tile")
        if len(edit) == 1:
            raise ValueError("Field background edit does not contain a value")
        tile = parsed["tiles"][tile_id]
        for field, value in edit.items():
            if field == "tile":
                continue
            identity = (tile_id, field)
            if identity in seen:
                raise ValueError("Field background edit repeats a tile field")
            seen.add(identity)
            if _write_field(output, tile, parsed["variant"], field, value):
                changed += 1
    result = bytes(output)
    reparsed = read(result, mim_data)
    if reparsed["variant"] != parsed["variant"] or reparsed["tileCount"] != parsed["tileCount"]:
        raise ValueError("Field background edit changed the MAP structure")
    return result, changed


def _ps_color(value: int) -> tuple[int, int, int]:
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return ((r << 3) + (r >> 2), (g << 3) + (g >> 2), (b << 3) + (b >> 2))


def _blend(destination: tuple[int, int, int], value: int, blend_type: int,
           force_black: bool) -> tuple[int, int, int] | None:
    if not force_black and value == 0:
        return None
    color = (0, 0, 0) if force_black else _ps_color(value)
    if blend_type == 4:
        return color
    old_r, old_g, old_b = destination
    r, g, b = color
    if blend_type == 0:
        # Deling uses the already-averaged red channel in its green and blue
        # expressions.  Preserve that exact renderer behavior for parity.
        r = (old_r + r) // 2
        return (r, (old_g + r) // 2, (old_b + r) // 2)
    if blend_type == 1:
        return (min(255, old_r + r), min(255, old_g + g), min(255, old_b + b))
    if blend_type == 2:
        return (max(0, old_r - r), max(0, old_g - g), max(0, old_b - b))
    if blend_type == 3:
        return (min(255, old_r + int(0.25 * r)),
                min(255, old_g + int(0.25 * g)),
                min(255, old_b + int(0.25 * b)))
    raise ValueError(f"Field background uses unsupported blend type {blend_type}")


def _tile_pixels(tile: dict, mim_data: bytes, pal_offset: int,
                 source_width: int) -> list[int]:
    palette_start = pal_offset + tile["palette"] * 512
    position = (pal_offset + 8192 + tile["texture"] * 128 +
                tile["sourceY"] * source_width)
    values = []
    if tile["depth"] == 2:
        position += tile["sourceX"] * 2
        row_stride = source_width * 2
        for y in range(16):
            for x in range(16):
                start = position + y * row_stride + x * 2
                if start + 2 > len(mim_data):
                    raise ValueError(f"Tile {tile['id']} reads beyond its MIM texture")
                values.append(struct.unpack_from("<H", mim_data, start)[0])
    elif tile["depth"] == 1:
        position += tile["sourceX"]
        for y in range(16):
            for x in range(16):
                start = position + y * source_width + x
                if start >= len(mim_data):
                    raise ValueError(f"Tile {tile['id']} reads beyond its MIM texture")
                index = mim_data[start]
                palette = palette_start + index * 2
                if palette + 2 > len(mim_data):
                    raise ValueError(f"Tile {tile['id']} reads beyond its MIM palette")
                values.append(struct.unpack_from("<H", mim_data, palette)[0])
    elif tile["depth"] in {0, 3}:
        position += tile["sourceX"] // 2
        for y in range(16):
            for byte_x in range(8):
                start = position + y * source_width + byte_x
                if start >= len(mim_data):
                    raise ValueError(f"Tile {tile['id']} reads beyond its MIM texture")
                indexes = (mim_data[start] & 0xF, mim_data[start] >> 4)
                for index in indexes:
                    palette = palette_start + index * 2
                    if palette + 2 > len(mim_data):
                        raise ValueError(f"Tile {tile['id']} reads beyond its MIM palette")
                    values.append(struct.unpack_from("<H", mim_data, palette)[0])
    else:
        raise ValueError(f"Tile {tile['id']} uses unsupported color depth {tile['depth']}")
    return values


def render(map_data: bytes, mim_data: bytes, *,
           active_states: set[tuple[int, int]] | None = None,
           enabled_layers: set[int] | None = None,
           hide_background: bool = False, highlight_tile: int | None = None) -> Image.Image:
    """Render the composed 16x16 tile background with Deling's filter rules."""
    parsed = read(map_data, mim_data)
    bounds = parsed["bounds"]
    width = bounds["left"] + bounds["right"] + 16
    height = bounds["top"] + bounds["bottom"] + 16
    if width <= 0 or height <= 0 or width * height > 40_000_000:
        raise ValueError(f"Field background render size {width}x{height} is unsafe")
    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()
    pal_offset, source_width = ((0, 1536) if len(mim_data) == OLD_MIM_SIZE
                                else (4096, 1664))
    if active_states is None:
        active_states = {(entry["parameter"], entry["state"])
                         for entry in parsed["parameterStates"] if entry["state"] == 0}
    if enabled_layers is None:
        enabled_layers = set(parsed["layers"])
    order = sorted(parsed["tiles"], key=lambda tile: (4096 - tile["z"], tile["id"]))
    if highlight_tile is not None:
        if not 0 <= highlight_tile < parsed["tileCount"]:
            raise ValueError("Highlighted background tile is out of range")
        order = [tile for tile in order if tile["id"] != highlight_tile]
        order.append(parsed["tiles"][highlight_tile])
    for tile in order:
        active = (tile["parameter"], tile["state"]) in active_states
        if ((hide_background or tile["parameter"] != 255) and not active) or \
                tile["layer"] not in enabled_layers:
            continue
        base_x = bounds["left"] + tile["x"]
        base_y = bounds["top"] + tile["y"]
        if base_x < 0 or base_y < 0 or base_x + 16 > width or base_y + 16 > height:
            raise ValueError(f"Tile {tile['id']} is outside Deling's computed render bounds")
        values = _tile_pixels(tile, mim_data, pal_offset, source_width)
        for index, value in enumerate(values):
            x, y = base_x + index % 16, base_y + index // 16
            color = _blend(pixels[x, y], value, tile["blendType"], not tile["draw"])
            if color is not None:
                pixels[x, y] = color
        if tile["id"] == highlight_tile:
            for edge in range(16):
                pixels[base_x + edge, base_y] = (255, 0, 0)
                pixels[base_x + edge, base_y + 15] = (255, 0, 0)
                pixels[base_x, base_y + edge] = (255, 0, 0)
                pixels[base_x + 15, base_y + edge] = (255, 0, 0)
    return image


def render_png(map_data: bytes, mim_data: bytes, **options: object) -> bytes:
    output = BytesIO()
    render(map_data, mim_data, **options).save(output, format="PNG", optimize=True)
    return output.getvalue()


def merge(vanilla_map: bytes, mim_data: bytes, mods: list[tuple[str, bytes]], path: str
          ) -> tuple[bytes | None, list[dict], str]:
    """Merge independent tile-field edits or request visible whole-file fallback."""
    try:
        baseline = read(vanilla_map, mim_data)
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    variant = baseline["variant"]
    fields = (_NEW_FIELDS if variant == "new" else
              _OLD_FIELDS if variant == "old" else _OLD_SHORT_FIELDS)
    claims: dict[tuple[int, str], list[tuple[str, object]]] = {}
    for mod_id, source in mods:
        if len(source) != len(vanilla_map):
            return None, [], f"{mod_id} changes the size of {path}"
        try:
            parsed = read(source, mim_data)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if parsed["variant"] != variant or parsed["tileCount"] != baseline["tileCount"]:
            return None, [], f"{mod_id} changes the proved structure of {path}"
        edits = []
        for tile_id, (before, after) in enumerate(zip(baseline["tiles"], parsed["tiles"])):
            edit = {"tile": tile_id}
            for field in fields:
                if before[field] != after[field]:
                    claims.setdefault((tile_id, field), []).append((mod_id, after[field]))
                    edit[field] = after[field]
            if len(edit) > 1:
                edits.append(edit)
        reconstructed, _ = apply_edits(vanilla_map, mim_data, edits)
        if reconstructed != source:
            return None, [], f"{mod_id} contains changes outside proved background tile fields"
    conflicts = []
    winners: dict[int, dict] = {}
    for (tile_id, field), values in claims.items():
        winners.setdefault(tile_id, {"tile": tile_id})[field] = values[-1][1]
        if len(values) > 1 and len({value for _, value in values}) > 1:
            conflicts.append({
                "unit": f"{path}:tile:{tile_id}:{field}",
                "winner": values[-1][0],
                "claimants": [mod_id for mod_id, _ in values],
            })
    output, _ = apply_edits(vanilla_map, mim_data, list(winners.values()))
    return output, conflicts, ""
