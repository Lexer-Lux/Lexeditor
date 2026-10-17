"""Optional private-image execution: never bundles or launches the retail game."""
import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess

import pytest

from plugins.ds1 import stamina_patch as native

ROOT = Path(__file__).resolve().parents[2]


def test_encumbrance_assembly_matches_runtime(tmp_path):
    if platform.system() != "Linux" or not all(shutil.which(tool) for tool in ("as", "ld", "objcopy")):
        pytest.skip("GNU binutils are needed for the independent assembly rebuild")
    plugin = Path(native.__file__).parent
    obj, elf = tmp_path / "code.o", tmp_path / "code.elf"
    subprocess.run(["as", "--64", "-o", str(obj), str(plugin / "encumbrance.S")], check=True)
    subprocess.run(["ld", "-T", str(plugin / "encumbrance.ld"), "-o", str(elf), str(obj)], check=True)
    for name, expected in (("factor", native.FACTOR_CODE), ("fraction", native.FRACTION_CODE)):
        output = tmp_path / (name + ".bin")
        subprocess.run(["objcopy", "-O", "binary", "--only-section=.text." + name, str(elf), str(output)], check=True)
        assert output.read_bytes() == expected


def test_private_image_native_recovery_and_encumbrance(tmp_path):
    filename = os.environ.get("LEXEDITOR_DS1_NATIVE_EXE")
    if not filename:
        pytest.skip("Private identified executable not supplied")
    original = Path(filename).read_bytes()
    native._pristine(original)
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64") or not shutil.which("gcc"):
        pytest.skip("Isolated native ABI execution needs x86-64 Linux and GCC")
    import mmap
    here = Path(__file__).parent
    adapter = tmp_path / "adapter.so"
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2",
                    str(here / "ds1_rules_native_adapter.c"),
                    str(here / "ds1_rules_factor_adapter.S"), "-o", str(adapter)], check=True)
    bridge = ctypes.CDLL(str(adapter))
    bridge.call_rate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    bridge.call_rate.restype = ctypes.c_float
    bridge.call_tier.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_uint, ctypes.c_uint]
    bridge.call_tier.restype = ctypes.c_int
    bridge.call_fraction.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float]
    bridge.call_fraction.restype = ctypes.c_float
    bridge.call_factor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    bridge.call_factor.restype = ctypes.c_float

    pe = struct.unpack_from("<I", original, 0x3c)[0]
    optional = pe + 24
    count = struct.unpack_from("<H", original, pe + 6)[0]
    section = optional + struct.unpack_from("<H", original, pe + 20)[0]
    image = mmap.mmap(-1, struct.unpack_from("<I", original, optional + 56)[0],
                     prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    address = ctypes.addressof(ctypes.c_char.from_buffer(image))
    def mapped(source):
        for index in range(count):
            _, rva, size, offset = struct.unpack_from("<4I", source, section + index * 40 + 8)
            image[rva:rva + size] = source[offset:offset + size]

    mapped(original)
    fraction = lambda value: bridge.call_fraction(address + 0x2e1a70, value, 100)
    samples = [i / 10 for i in range(1101)]
    reference = [fraction(value) for value in samples]
    mapped(native.transform(original, {**native.DEFAULT_RULES, "lightRecovery": 101}))
    assert [fraction(value) for value in samples] == pytest.approx(reference, abs=1e-6)

    rules = {**native.DEFAULT_RULES, "baseRecovery": 60, "lightLimit": 30,
             "mediumLimit": 60, "heavyLimit": 120,
             **dict(zip(native.RECOVERY_KEYS, (105, 115, 95, 60, 15)))}
    changed = native.transform(original, rules)
    mapped(changed)
    assert native.identify(changed, original) == rules
    for weight, tier in ((0, 1), (30, 1), (30.01, 2), (60, 2), (60.01, 3), (120, 3), (120.01, 4)):
        assert bridge.call_tier(address + 0x2e1a10, weight, 100, 0, 0) == tier
    assert bridge.call_tier(address + 0x2e1a10, 10, 100, 1, 0) == 0
    assert bridge.call_tier(address + 0x2e1a10, 10, 100, 0, 1) == 4
    for weight, expected in ((0, 0), (15, .5), (30, 1), (45, .5), (60, 1), (90, .5), (120, 1), (121, 0)):
        assert fraction(weight) == pytest.approx(expected, abs=1e-6)
    # Test-only return stub at the continuation isolates the replacement's factor output.
    # This stub is never part of the shipped patch.
    image[0x357013:0x357017] = bytes.fromhex("0f28c6c3")
    for tier, key in enumerate(native.RECOVERY_KEYS):
        assert bridge.call_factor(address + native.FACTOR_RVA, tier) == pytest.approx(rules[key] / 100)

    player = ctypes.create_string_buffer(0x500)
    controller = ctypes.create_string_buffer(0x80)
    struct.pack_into("<Q", player, 0x278, ctypes.addressof(controller))
    struct.pack_into("<ii", player, 0x3f8, 0, 160)
    rows = [ctypes.create_string_buffer(368) for _ in range(4)]
    nodes = [ctypes.create_string_buffer(0x50) for _ in rows]
    for index, (row, node) in enumerate(zip(rows, nodes)):
        struct.pack_into("<i", row, 0xb8, (10, 20, -2, 500)[index])
        struct.pack_into("<I", node, 0x14, int(index == 3))
        struct.pack_into("<Q", node, 0x38, ctypes.addressof(row))
        struct.pack_into("<Q", node, 0x40, ctypes.addressof(nodes[index + 1]) if index < 3 else 0)
    for base in (0, 45, 60, 200):
        struct.pack_into("<f", image, native.BASELINE_RVA, base)
        for active in (False, True):
            struct.pack_into("<Q", controller, 8, ctypes.addressof(nodes[0]) if active else 0)
            assert bridge.call_rate(address + 0x35ed00, ctypes.addressof(player)) == base + (28 if active else 0)
    image.close()
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == native.ORIGINAL_SHA256
