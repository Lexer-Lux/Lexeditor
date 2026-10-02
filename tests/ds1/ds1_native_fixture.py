"""Synthetic native-rule integration fixtures; no proprietary game data."""
import hashlib
import struct

from ds1_effects_fixture import make_effects_archive, wrap
from plugins.ds1.formats import inflate, members, ItemDocument
from plugins.ds1 import stamina_patch as native, load_bands_patch as bands_patch


def make_native_archive():
    source = make_effects_archive()
    plain = bytearray(inflate(source))
    table = members(plain)["EquipParamWeapon.param"]
    struct.pack_into("<i", plain, table.offset + 48, 1453000)
    return wrap(plain, source)


def fake_executable(monkeypatch):
    # Small, inert PE-shaped image. Its instructions are never executed.
    # The layout exercises both fixed-span and bounded-extension ownership.
    data = bytearray((i * 17 + 3) % 256 for i in range(4160))
    pe, optional, optional_size = 128, 152, 240
    last = optional + optional_size + 8 * 40
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<H", data, pe + 6, 9)
    struct.pack_into("<H", data, pe + 20, optional_size)
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 4, 2048)
    struct.pack_into("<I", data, optional + 56, 8192)
    struct.pack_into("<II", data, optional + 144, 4096, 64)
    struct.pack_into("<4I", data, last + 8, 2048, 6144, 2048, 2048)
    struct.pack_into("<I", data, last + 36, 0x60000020)
    offsets = {"BASELINE_OFFSET": 1024, "LIGHT_OFFSET": 1032, "MEDIUM_OFFSET": 1036,
               "FACTOR_OFFSET": 1152, "FRACTION_OFFSET": 1280, "OVERLOAD_DISP_OFFSET": 1040}
    for key, value in offsets.items():
        monkeypatch.setattr(native, key, value)
    for key in ("BASELINE_OFFSET", "FACTOR_OFFSET", "FRACTION_OFFSET"):
        monkeypatch.setattr(bands_patch, key, offsets[key])
    monkeypatch.setattr(bands_patch, "CLASS_OFFSET", 1536)
    monkeypatch.setattr(bands_patch, "BLOCK_OFFSET", 4096)
    monkeypatch.setattr(bands_patch, "BLOCK_RVA", 8192)
    struct.pack_into("<f", data, offsets["BASELINE_OFFSET"], 45)
    struct.pack_into("<f", data, offsets["LIGHT_OFFSET"], .25)
    struct.pack_into("<f", data, offsets["MEDIUM_OFFSET"], .5)
    data = bytes(data)
    monkeypatch.setattr(native, "ORIGINAL_SIZE", len(data))
    monkeypatch.setattr(native, "MAX_NATIVE_SIZE", len(data) + bands_patch.EXTENSION_SIZE)
    monkeypatch.setattr(native, "ORIGINAL_SHA256", hashlib.sha256(data).hexdigest())
    return data
