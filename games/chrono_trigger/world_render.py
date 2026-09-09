"""Read-only raster previews for Chrono Trigger Steam overworld L1/L2."""

from __future__ import annotations

from dataclasses import dataclass
import struct

from .data import OverlayStore
from .scene_render import png_rgba
from .worlds import load_worlds


@dataclass(frozen=True)
class Corner:
    chip: int
    palette: int
    flip_x: bool
    flip_y: bool
    priority: bool


def _palette(raw: bytes) -> list[tuple[int, int, int, int]]:
    if len(raw) < 2 + 512:
        raise ValueError("Chrono Trigger world palette is truncated")
    colors = []
    for index in range(256):
        value = struct.unpack_from("<H", raw, 2 + index * 2)[0]
        colors.append((
            round((value & 0x1F) * 255 / 31),
            round(((value >> 5) & 0x1F) * 255 / 31),
            round(((value >> 10) & 0x1F) * 255 / 31),
            255,
        ))
    return colors


def _unpack(raw: bytes) -> bytes:
    if len(raw) < 4:
        raise ValueError("Chrono Trigger world cg sheet is shorter than its four-byte header")
    packed = raw[4:]
    pixels = bytearray(len(packed) * 2)
    pos = 0
    for value in packed:
        pixels[pos] = (value >> 4) & 0x0F
        pixels[pos + 1] = value & 0x0F
        pos += 2
    if len(pixels) % 128:
        raise ValueError("Chrono Trigger world cg sheet does not decode to 128-pixel scanlines")
    return bytes(pixels)


def _chips(store: OverlayStore, indices: list[int], source: str) -> tuple[list[bytes], list[dict]]:
    bitmap = bytearray(0x10000)
    sheets = []
    for slot, chipset in enumerate(indices):
        if chipset == 0x80:
            continue
        path = f"Game/world/map_bin/cg{chipset}.bin"
        raw, _origin = store.read(path, source)
        pixels = _unpack(raw)
        destination = slot * 0x2000
        if destination + len(pixels) > len(bitmap):
            raise ValueError(f"Chrono Trigger world cg sheet {chipset} exceeds its slot")
        bitmap[destination:destination + len(pixels)] = pixels
        sheets.append({"slot": slot, "chipset": chipset, "path": path, "pixelBytes": len(pixels)})
    chips = []
    for chip_index in range(len(bitmap) // 64):
        x0 = (chip_index % 16) * 8
        y0 = (chip_index // 16) * 8
        chip = bytearray(64)
        cursor = 0
        for y in range(8):
            start = (y0 + y) * 128 + x0
            chip[cursor:cursor + 8] = bitmap[start:start + 8]
            cursor += 8
        chips.append(bytes(chip))
    return chips, sheets


def _assembly(store: OverlayStore, index: int, source: str) -> tuple[list[tuple[Corner, ...]], str]:
    path = f"Game/world/Chip/Chip_{index:04d}.dat"
    raw, _origin = store.read(path, source)
    required = 512 * 4 * 2
    if len(raw) < required:
        raise ValueError(f"Chrono Trigger world Chip table is truncated: {path}")
    tiles = []
    cursor = 0
    for _ in range(512):
        corners = []
        for _corner in range(4):
            value = struct.unpack_from("<H", raw, cursor)[0]
            cursor += 2
            corners.append(Corner(
                chip=value & 0x03FF,
                palette=((value >> 10) & 0x07) * 16,
                priority=bool(value & 0x2000),
                flip_x=bool(value & 0x4000),
                flip_y=bool(value & 0x8000),
            ))
        tiles.append(tuple(corners))
    return tiles, path


def _draw(output: bytearray, width: int, x0: int, y0: int, chip: bytes,
          corner: Corner, colors: list[tuple[int, int, int, int]]) -> None:
    for y in range(8):
        sy = 7 - y if corner.flip_y else y
        for x in range(8):
            sx = 7 - x if corner.flip_x else x
            pixel = chip[sy * 8 + sx]
            color = colors[(corner.palette + pixel) & 0xFF]
            dest = ((y0 + y) * width + x0 + x) * 4
            output[dest:dest + 4] = bytes((color[0], color[1], color[2], 0 if pixel == 0 else 255))


def render_world_layer(store: OverlayStore, world_id: int, layer: int,
                       source: str = "mine") -> tuple[bytes, dict]:
    layer = int(layer)
    if layer not in {1, 2}:
        raise ValueError("Overworld raster preview currently supports layer 1 or 2")
    worlds = load_worlds(store, source)
    world_id = int(world_id)
    if not 0 <= world_id < len(worlds["rows"]):
        raise ValueError(f"Unknown Chrono Trigger overworld: {world_id}")
    row = worlds["rows"][world_id]
    values = row["values"]

    map_id = int(values["map"])
    map_path = f"Game/world/Map/Map_{map_id:04d}.dat"
    raw, _origin = store.read(map_path, source)
    tile_count = 96 * 64
    required = tile_count * 2
    if len(raw) < required:
        raise ValueError(f"Chrono Trigger world Map data is truncated: {map_path}")
    start = 0 if layer == 1 else tile_count
    tile_ids = list(raw[start:start + tile_count])
    if layer == 2:
        tile_ids = [value + 256 for value in tile_ids]

    palette_id = int(values["palette"])
    palette_path = f"Game/world/plt_bin/plt{palette_id}.bin"
    palette_raw, _origin = store.read(palette_path, source)
    colors = _palette(palette_raw)
    chipset_ids = [int(values[f"chipL12_{index}"]) for index in range(8)]
    chips, sheets = _chips(store, chipset_ids, source)
    assembly_id = int(values["assemblyL12"])
    assembly, assembly_path = _assembly(store, assembly_id, source)

    width, height = 96 * 16, 64 * 16
    output = bytearray(width * height * 4)
    for tile_y in range(64):
        for tile_x in range(96):
            tile_id = tile_ids[tile_y * 96 + tile_x]
            if not 0 <= tile_id < len(assembly):
                continue
            for corner_index, corner in enumerate(assembly[tile_id]):
                if not 0 <= corner.chip < len(chips):
                    continue
                x = tile_x * 16 + (corner_index % 2) * 8
                y = tile_y * 16 + (corner_index // 2) * 8
                _draw(output, width, x, y, chips[corner.chip], corner, colors)

    png = png_rgba(width, height, bytes(output))
    return png, {
        "worldId": world_id,
        "worldName": row.get("name", f"World {world_id}"),
        "layer": layer,
        "width": width,
        "height": height,
        "tileWidth": 96,
        "tileHeight": 64,
        "map": map_id,
        "mapPath": map_path,
        "palette": palette_id,
        "palettePath": palette_path,
        "chipsets": chipset_ids,
        "staticSheets": sheets,
        "assembly": assembly_id,
        "assemblyPath": assembly_path,
        "composition": "isolated-layer",
        "transparentColorZero": True,
    }
