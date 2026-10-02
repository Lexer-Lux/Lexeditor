"""Variable-band machine-code verification, separate from installed-game acceptance."""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from plugins.ds1 import load_bands as bands, load_bands_patch as patch, stamina_patch as native


def test_variable_band_assembly_matches_embedded_bytes(tmp_path):
    if platform.system() != "Linux" or not all(shutil.which(t) for t in ("as", "ld", "objcopy")):
        pytest.skip("Independent assembly rebuild requires GNU binutils on Linux")
    plugin = Path(patch.__file__).parent
    obj, elf = tmp_path / "bands.o", tmp_path / "bands.elf"
    subprocess.run(["as", "--64", "-o", str(obj), str(plugin / "load_bands.S")], check=True)
    subprocess.run(["ld", "-T", str(plugin / "load_bands.ld"), "-o", str(elf), str(obj)], check=True)
    for section, expected in (("classifier", patch.CLASSIFIER), ("recovery", patch.RECOVERY),
                              ("factor", patch.FACTOR), ("fraction", patch.FRACTION)):
        output = tmp_path / (section + ".bin")
        subprocess.run(["objcopy", "-O", "binary", "--only-section=." + section,
                        str(elf), str(output)], check=True)
        assert output.read_bytes() == expected
    assert patch.CLASSIFIER_OFFSET + len(patch.CLASSIFIER) <= patch.RECOVERY_OFFSET
    assert patch.RECOVERY_OFFSET + len(patch.RECOVERY) <= patch.TABLE_OFFSET
    assert patch.TABLE_OFFSET + bands.MAX_BANDS * 32 <= patch.JSON_OFFSET
    assert len(patch.FACTOR) == 41 and len(patch.FRACTION) == 151


def test_variable_band_machine_code_in_isolated_process(tmp_path):
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64") or not shutil.which("gcc"):
        pytest.skip("Machine-code execution requires x86-64 Linux and GCC")
    result = subprocess.run([sys.executable, str(Path(__file__)), "--execute", str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    assert evidence["comparisons"] > 20000 and evidence["configurations"] >= 6
    assert evidence["factorCallSite"] is True


def test_private_executable_band_roundtrip(tmp_path):
    filename = os.environ.get("LEXEDITOR_DS1_NATIVE_EXE")
    if not filename:
        pytest.skip("Private identified executable not supplied")
    original = Path(filename).read_bytes()
    native._pristine(original)
    config = bands.project_defaults()
    config["bands"], _ = bands.split(config["bands"], 1, 15)
    config["bands"] = bands.edit(config["bands"], 5, "recovery", 120)
    rules = bands.native_projection({"baseRecovery": 70, **config})
    changed = native.transform(original, rules)
    assert native.identify(changed, original) == rules
    assert changed[patch.BLOCK_OFFSET + patch.EXTENSION_SIZE:] == original[patch.BLOCK_OFFSET:]
    # Private-image input is only read; no executable is emitted or launched.
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == native.ORIGINAL_SHA256


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def reference(rules, weight, capacity, special, forced):
    if capacity == 0:
        ratio = math.nan if weight == 0 else math.copysign(math.inf, weight)
    else:
        ratio = f32(f32(weight) / f32(capacity))
    row = next((r for r in bands.runtime_rows(rules["bands"])
                if math.isnan(ratio) or ratio <= f32(r[0])),
               bands.runtime_rows(rules["bands"])[-1])
    _, profile, recovery, lower, span = row
    if not span or math.isnan(ratio):
        fraction = 0.0
    else:
        fraction = min(1.0, max(0.0, f32(f32(ratio - f32(lower)) / f32(span))))
    if forced:
        return 4, f32(rules["forcedRecovery"] / 100), fraction
    if special and profile == 1 and rules["specialLight"]["enabled"]:
        return 0, f32(rules["specialLight"]["recovery"] / 100), fraction
    return profile, f32(recovery), fraction


def execute(work):
    """Run selectors in a child process, optionally using the supplied private image."""
    import mmap
    adapter = work / "bands-abi.so"
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(HERE / "bands_abi.c"), str(HERE / "bands_factor_abi.S"),
                    "-o", str(adapter)], check=True)
    bridge = ctypes.CDLL(str(adapter))
    signature = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_int]
    bridge.bands_class.argtypes = signature
    bridge.bands_class.restype = ctypes.c_int
    bridge.bands_rate.argtypes = signature
    bridge.bands_rate.restype = ctypes.c_float
    bridge.bands_fraction.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float]
    bridge.bands_fraction.restype = ctypes.c_float
    bridge.bands_factor.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_int]
    bridge.bands_factor.restype = ctypes.c_float

    configs = [bands.project_defaults()]
    split = bands.project_defaults()
    split["bands"], _ = bands.split(split["bands"], 1, 15)
    configs.append(split)
    custom = bands.project_defaults()
    custom["bands"] = [
        {"id": 1, "name": "Feather", "upper": 15, "movement": 1, "recovery": 120},
        {"id": 2, "name": "Light", "upper": 35, "movement": 1, "recovery": 100},
        {"id": 3, "name": "Medium", "upper": 65, "movement": 2, "recovery": 90},
        {"id": 4, "name": "Heavy", "upper": 110, "movement": 3, "recovery": 75},
        {"id": 5, "name": "Burden", "upper": None, "movement": 4, "recovery": 50},
    ]
    custom["specialLight"] = {"enabled": True, "recovery": 137}
    custom["forcedRecovery"] = 23
    configs.append(custom)
    configs.append({**custom, "specialLight": {"enabled": False, "recovery": 199}})
    for profile in (1, 2, 3, 4):
        configs.append({**bands.project_defaults(), "bands": [
            {"id": 1, "name": "Every load", "upper": None, "movement": profile, "recovery": 62}]})
    many = [{"id": i + 1, "name": f"Band {i}", "upper": float(i + 1) if i < 31 else None,
             "movement": i % 4 + 1, "recovery": float(i * 31)} for i in range(32)]
    configs.append({**bands.project_defaults(), "bands": many})

    image = mmap.mmap(-1, patch.BLOCK_RVA + patch.EXTENSION_SIZE,
                     prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    address = ctypes.addressof(ctypes.c_char.from_buffer(image))
    filename = os.environ.get("LEXEDITOR_DS1_NATIVE_EXE")
    original = Path(filename).read_bytes() if filename else None
    if original is not None:
        native._pristine(original)
    comparisons = 0
    fraction_entry = patch.FRACTION_RVA - 11
    original_samples = {}
    if original is not None:
        pe = struct.unpack_from("<I", original, 0x3C)[0]
        section = pe + 24 + struct.unpack_from("<H", original, pe + 20)[0]
        for index in range(struct.unpack_from("<H", original, pe + 6)[0]):
            _, rva, size, offset = struct.unpack_from("<4I", original, section + index * 40 + 8)
            image[rva:rva + size] = original[offset:offset + size]
        for step in range(1302):
            weight = step / 1000
            original_samples[step] = (
                bridge.bands_fraction(address + fraction_entry, weight, 1),
                [bridge.bands_class(address + patch.CLASS_RVA, weight, 1, special, forced)
                 for special in (0, 1) for forced in (0, 1)])
    try:
        for config in configs:
            rules = bands.native_projection({"baseRecovery": 60, **config})
            if original is not None:
                data = native.transform(original, rules)
                pe = struct.unpack_from("<I", data, 0x3C)[0]
                section = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
                for index in range(struct.unpack_from("<H", data, pe + 6)[0]):
                    _, rva, size, offset = struct.unpack_from("<4I", data, section + index * 40 + 8)
                    image[rva:rva + size] = data[offset:offset + size]
            else:
                image[patch.BLOCK_RVA:patch.BLOCK_RVA + patch.EXTENSION_SIZE] = patch.block(rules)
                image[patch.CLASS_RVA:patch.CLASS_RVA + 5] = b"\xe9" + struct.pack(
                    "<i", patch.BLOCK_RVA + patch.CLASSIFIER_OFFSET - patch.CLASS_RVA - 5)
                image[patch.FACTOR_RVA:patch.FACTOR_RVA + len(patch.FACTOR)] = patch.FACTOR
                image[patch.FRACTION_RVA:patch.FRACTION_RVA + len(patch.FRACTION)] = patch.FRACTION
                # Original test scaffolding with the same entry contract, not retail bytes.
                entry = bytes.fromhex("4883ec180f28d80f293424")
                image[fraction_entry:fraction_entry + len(entry)] = entry
                end = patch.FRACTION_RVA + len(patch.FRACTION)
                epilogue = bytes.fromhex("f30f10000f2834244883c418c3")
                image[end:end + len(epilogue)] = epilogue
            if config is configs[0]:
                for step, (fraction, profiles) in original_samples.items():
                    weight = step / 1000
                    assert abs(bridge.bands_fraction(address + fraction_entry, weight, 1) - fraction) < 1e-6
                    assert [bridge.bands_class(address + patch.CLASS_RVA, weight, 1, special, forced)
                            for special in (0, 1) for forced in (0, 1)] == profiles
            # Test-only capacity getter and continuation. Never part of shipped code.
            # Reads RCX, exercising the factor patch's player-pointer forwarding.
            image[0x362340:0x362345] = bytes.fromhex("f30f1001c3")
            image[0x357013:0x357019] = bytes.fromhex("0f28c641ffe4")
            samples = [i / 1000 for i in range(-1, 1302)] + [math.nan, math.inf, -math.inf]
            for band in rules["bands"]:
                if band["upper"] is not None:
                    edge = f32(band["upper"] / 100)
                    word = struct.unpack("<I", struct.pack("<f", edge))[0]
                    samples.extend(struct.unpack("<f", struct.pack("<I", word + delta))[0]
                                   for delta in (-1, 0, 1))
            for weight, capacity in [(load, 1.0) for load in samples] + [(15, 100), (0, 0), (1, 0)]:
                expected_fraction = reference(rules, weight, capacity, False, False)[2]
                actual_fraction = bridge.bands_fraction(address + fraction_entry, weight, capacity)
                assert abs(actual_fraction - expected_fraction) < 1e-5, (rules, weight, actual_fraction, expected_fraction)
                for special in (0, 1):
                    for forced in (0, 1):
                        profile, recovery, _ = reference(rules, weight, capacity, special, forced)
                        actual = bridge.bands_class(address + patch.CLASS_RVA, weight, capacity, special, forced)
                        rate = bridge.bands_rate(address + patch.BLOCK_RVA + patch.RECOVERY_OFFSET,
                                                  weight, capacity, special, forced)
                        player = ctypes.c_float(capacity)
                        factor = bridge.bands_factor(address + patch.FACTOR_RVA, ctypes.byref(player),
                                                       weight, special, forced)
                        assert actual == profile, (weight, actual, profile)
                        assert abs(rate - recovery) < 1e-6, (weight, rate, recovery)
                        assert abs(factor - recovery) < 1e-6, (weight, factor, recovery)
                        comparisons += 3
    finally:
        image.close()
    if filename:
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == native.ORIGINAL_SHA256
    print(json.dumps({"comparisons": comparisons, "configurations": len(configs),
                      "factorCallSite": True, "privateImage": bool(original),
                      "originalComparisonSamples": len(original_samples)}))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--execute":
        raise SystemExit("Use pytest for this verifier")
    execute(Path(sys.argv[2]))
