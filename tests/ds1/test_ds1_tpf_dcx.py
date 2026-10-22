"""DCX-wrapped textures preview: the menu icon sheets show up bare otherwise.

Clicking an icon's preview lands on its menu sheet (menu/menu_1.tpf.dcx
and kin): a TPF inside a DCX wrapper. The preview code inflated the
bytes but then read the .dcx filename for the type, found no match,
and the record showed no thumbnail or preview. Both listing and PNG
rendering now read the inner type.
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.assets import list_textures, texture_png


def make_dds(width=8, height=8):
    head = bytearray(128)
    head[0:4] = b"DDS "
    struct.pack_into("<I", head, 4, 124)
    struct.pack_into("<I", head, 8, 0x1 | 0x2 | 0x4 | 0x1000)
    struct.pack_into("<2I", head, 12, height, width)
    struct.pack_into("<I", head, 20, width * 4)
    struct.pack_into("<I", head, 28, 1)
    struct.pack_into("<I", head, 76, 32)
    struct.pack_into("<I", head, 80, 0x41)
    struct.pack_into("<I", head, 88, 32)
    struct.pack_into("<4I", head, 92, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    struct.pack_into("<I", head, 108, 0x1000)
    pixels = bytearray()
    for row in range(height):
        for column in range(width):
            pixels += bytes((255 if (row + column) % 2 else 0, 0 if (row + column) % 2 else 255, 128, 255))
    return bytes(head) + bytes(pixels)


def make_tpf(name):
    blob = make_dds()
    encoded = name.encode("shift_jis") + b"\x00"
    head = bytearray(16)
    head[0:4] = b"TPF\x00"
    struct.pack_into("<I", head, 8, 1)
    return bytes(head) + struct.pack("<5I", 16 + 20 + len(encoded), len(blob), 0, 16 + 20, 0) + encoded + blob


def dcx_wrap(plain):
    compressed = zlib.compress(bytes(plain), 9)
    header = bytearray.fromhex("44435800000100000000001800000024000000240000002c4443530000000000000000004443500044464c540000002009000000000000000000000000000000000101004443410000000008")
    struct.pack_into(">II", header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def test_list_textures_sees_through_dcx():
    wrapped = dcx_wrap(make_tpf("Icon00"))
    found = list_textures(wrapped, "menu/menu_1.tpf.dcx")
    assert [(texture["name"], texture["width"], texture["height"]) for texture in found] == [("Icon00", 8, 8)]


def test_texture_png_renders_through_dcx():
    wrapped = dcx_wrap(make_tpf("Icon00"))
    png = texture_png(wrapped, "menu/menu_1.tpf.dcx", "", 0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_plain_tpf_still_lists():
    found = list_textures(make_tpf("Icon00"), "menu/menu_1.tpf")
    assert [texture["name"] for texture in found] == ["Icon00"]
