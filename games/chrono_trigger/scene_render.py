"""Read-only raster previews for Chrono Trigger Steam scene layers.

The renderer follows CTViewer's documented PC data path: ``mapinfo`` selects a
BGSetTable, ChipTable, palette and MapTable; each referenced ``cg*.bin`` is a
128-pixel-wide packed 4bpp sheet after a four-byte header; PC ChipTable corners
are three bytes each.  L1 and L2 are rendered separately so Lexeditor does not
pretend to emulate the game's main/sub-screen blending or priority rules.
"""

from __future__ import annotations

import binascii
from dataclasses import dataclass
import struct
import zlib

from .data import OverlayStore, load_scene
from .scene_maps import load_scene_map


@dataclass(frozen=True)
class Corner:
    chip: int
    palette: int
    flip_x: bool
    flip_y: bool
    priority: bool


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Encode one RGBA8 image using PNG filter type 0 and zlib."""
    if width <= 0 or height <= 0 or len(pixels) != width * height * 4:
        raise ValueError("Invalid RGBA image dimensions")
    stride = width * 4
    scanlines = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(scanlines, 9)) + _png_chunk(b"IEND", b"")


def _decode_palette(raw: bytes) -> list[tuple[int, int, int, int]]:
    if len(raw) < 2 + 256 * 2:
        raise ValueError("Chrono Trigger scene palette is truncated")
    colors = []
    for index in range(256):
        value = struct.unpack_from("<H", raw, 2 + index * 2)[0]
        red = round((value & 0x1F) * 255 / 31)
        green = round(((value >> 5) & 0x1F) * 255 / 31)
        blue = round(((value >> 10) & 0x1F) * 255 / 31)
        colors.append((red, green, blue, 255))
    return colors


def _unpack_sheet(raw: bytes) -> bytes:
    if len(raw) < 4:
        raise ValueError("Chrono Trigger cg sheet is shorter than its four-byte header")
    packed = raw[4:]
    pixels = bytearray(len(packed) * 2)
    cursor = 0
    for value in packed:
        pixels[cursor] = (value >> 4) & 0x0F
        pixels[cursor + 1] = value & 0x0F
        cursor += 2
    if len(pixels) % 128:
        raise ValueError("Chrono Trigger cg sheet does not decode to 128-pixel scanlines")
    return bytes(pixels)


def _static_chips(store: OverlayStore, tileset_index: int, source: str) -> tuple[list[bytes], dict]:
    path = f"Game/field/BGSetTable/bgsettable_{tileset_index}.dat"
    raw, _origin = store.read(path, source)
    if len(raw) < 8:
        raise ValueError(f"Chrono Trigger BGSetTable is truncated: {path}")
    chipsets = list(raw[:8])
    bitmap = bytearray(0x14000)
    used = []
    animated = None
    for slot, chipset in enumerate(chipsets):
        if chipset == 0xFF:
            continue
        cg_path = f"Game/field/map_bin/cg{chipset}.bin"
        sheet, _cg_origin = store.read(cg_path, source)
        pixels = _unpack_sheet(sheet)
        if slot == 6:
            animated = {"slot": slot, "chipset": chipset, "path": cg_path, "pixelBytes": len(pixels)}
            continue
        destination = slot * 0x2000 if slot < 7 else (slot - 1) * 0x2000
        if destination + len(pixels) > len(bitmap):
            raise ValueError(f"Chrono Trigger cg sheet {chipset} exceeds the static tileset buffer")
        bitmap[destination:destination + len(pixels)] = pixels
        used.append({"slot": slot, "chipset": chipset, "path": cg_path, "pixelBytes": len(pixels)})

    # CTViewer treats the assembled bitmap as a 128-pixel-wide sheet, 16 chips per row.
    chip_count = len(bitmap) // 64
    chips = []
    for chip_index in range(chip_count):
        x0 = (chip_index % 16) * 8
        y0 = (chip_index // 16) * 8
        chip = bytearray(64)
        pos = 0
        for y in range(8):
            start = (y0 + y) * 128 + x0
            chip[pos:pos + 8] = bitmap[start:start + 8]
            pos += 8
        chips.append(bytes(chip))
    return chips, {"bgSetPath": path, "chipsets": chipsets, "staticSheets": used, "animatedSheet": animated}


def _assembly(store: OverlayStore, assembly_index: int, source: str) -> tuple[list[tuple[Corner, ...]], str]:
    path = f"Game/field/ChipTable/ChipTable_{assembly_index:04d}.dat"
    raw, _origin = store.read(path, source)
    required = 512 * 4 * 3
    if len(raw) < required:
        raise ValueError(f"Chrono Trigger PC ChipTable is truncated: {path}")
    tiles = []
    cursor = 0
    for _tile_index in range(512):
        corners = []
        for _corner in range(4):
            value = struct.unpack_from("<H", raw, cursor)[0]
            flags = raw[cursor + 2]
            cursor += 3
            corners.append(Corner(
                chip=value & 0x03FF,
                palette=((value >> 12) & 0x0F) * 16,
                flip_x=bool(value & 0x0400),
                flip_y=bool(value & 0x0800),
                priority=bool(flags & 0x01),
            ))
        tiles.append(tuple(corners))
    return tiles, path


def _draw_chip(output: bytearray, width: int, x0: int, y0: int, chip: bytes,
               corner: Corner, palette: list[tuple[int, int, int, int]], *, transparent_zero: bool) -> None:
    for y in range(8):
        sy = 7 - y if corner.flip_y else y
        for x in range(8):
            sx = 7 - x if corner.flip_x else x
            pixel = chip[sy * 8 + sx]
            color = palette[(corner.palette + pixel) & 0xFF]
            alpha = 0 if transparent_zero and pixel == 0 else color[3]
            dest = ((y0 + y) * width + x0 + x) * 4
            output[dest:dest + 4] = bytes((color[0], color[1], color[2], alpha))


def render_scene_layer(store: OverlayStore, scene_id: int, layer: int,
                       source: str = "mine") -> tuple[bytes, dict]:
    """Render L1 or L2 as an independent RGBA PNG and return provenance metadata."""
    layer = int(layer)
    if layer not in {1, 2}:
        raise ValueError("Scene raster preview currently supports layer 1 or 2")
    entries = {number: path for number, path in store.scene_entries()}
    scene_id = int(scene_id)
    if scene_id not in entries:
        raise ValueError(f"Unknown Chrono Trigger scene: {scene_id}")
    scene = load_scene(store, scene_id, entries[scene_id], source)
    values = scene["values"]
    map_payload = load_scene_map(store, scene_id, source)
    layer_payload = map_payload["layers"][f"layer{layer}"]
    tile_width = int(layer_payload["width"])
    tile_height = int(layer_payload["height"])
    width, height = tile_width * 16, tile_height * 16
    if width * height > 1024 * 1024:
        raise ValueError("Chrono Trigger scene raster exceeds the one-megapixel preview limit")

    palette_path = f"Game/field/palette_bin/plt{int(values['palette'])}.bin"
    palette_raw, _palette_origin = store.read(palette_path, source)
    palette = _decode_palette(palette_raw)
    chips, chip_meta = _static_chips(store, int(values["tilesetL12"]), source)
    assembly, assembly_path = _assembly(store, int(values["tilesetL12Assembly"]), source)

    output = bytearray(width * height * 4)
    for tile_y in range(tile_height):
        for tile_x in range(tile_width):
            tile_id = int(layer_payload["tiles"][tile_y * tile_width + tile_x])
            if not 0 <= tile_id < len(assembly):
                continue
            tile = assembly[tile_id]
            for corner_index, corner in enumerate(tile):
                if not 0 <= corner.chip < len(chips):
                    continue
                corner_x = tile_x * 16 + (corner_index % 2) * 8
                corner_y = tile_y * 16 + (corner_index // 2) * 8
                _draw_chip(output, width, corner_x, corner_y, chips[corner.chip], corner, palette,
                           transparent_zero=True)

    png = png_rgba(width, height, bytes(output))
    metadata = {
        "sceneId": scene_id,
        "layer": layer,
        "width": width,
        "height": height,
        "tileWidth": tile_width,
        "tileHeight": tile_height,
        "mapId": int(values["mapIndex"]),
        "mapPath": map_payload["path"],
        "palette": int(values["palette"]),
        "palettePath": palette_path,
        "tileset": int(values["tilesetL12"]),
        "assembly": int(values["tilesetL12Assembly"]),
        "assemblyPath": assembly_path,
        "transparentColorZero": True,
        "animatedChipsRendered": False,
        "composition": "isolated-layer",
        **chip_meta,
    }
    return png, metadata
