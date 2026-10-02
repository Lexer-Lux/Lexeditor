"""Synthetic native-rule integration fixtures; no proprietary game data."""
import hashlib
import struct

from ds1_effects_fixture import make_effects_archive, wrap
from plugins.ds1.formats import inflate, members, ItemDocument
from plugins.ds1 import stamina_patch as native


def make_native_archive():
    source = make_effects_archive()
    plain = bytearray(inflate(source))
    table = members(plain)["EquipParamWeapon.param"]
    # The existing fixture's first weapon becomes the real shield identity.
    struct.pack_into("<i", plain, table.offset + 48, 1453000)
    return wrap(plain, source)


def fake_executable(monkeypatch):
    data = bytearray((i * 17 + 3) % 256 for i in range(4096))
    offsets = {"BASELINE_OFFSET": 32, "LIGHT_OFFSET": 40, "MEDIUM_OFFSET": 44,
               "FACTOR_OFFSET": 256, "FRACTION_OFFSET": 512, "OVERLOAD_DISP_OFFSET": 64}
    for key, value in offsets.items():
        monkeypatch.setattr(native, key, value)
    struct.pack_into("<f", data, 32, 45)
    struct.pack_into("<f", data, 40, .25)
    struct.pack_into("<f", data, 44, .5)
    data = bytes(data)
    monkeypatch.setattr(native, "ORIGINAL_SIZE", len(data))
    monkeypatch.setattr(native, "ORIGINAL_SHA256", hashlib.sha256(data).hexdigest())
    return data
