"""Variable load-band editing, migration, native tables and selector execution."""
from copy import deepcopy
import ctypes
import math
import platform
import shutil
import struct
import subprocess

import pytest

from plugins.ds1 import load_bands as bands, load_bands_patch as patch


def config():
    return {"baseRecovery": 45.0, **bands.project_defaults()}


def native(value=None):
    return bands.native_projection(config() if value is None else value)


@pytest.mark.parametrize("identity,at", [(1, 12.5), (2, 35), (3, 75), (4, 150)])
def test_split_preserves_inputs_identity_and_gameplay(identity, at):
    before = config()
    saved = deepcopy(before)
    after, new_id = bands.split(before["bands"], identity, at)
    assert before == saved
    assert new_id == 5
    assert [b["id"] for b in after if b["id"] != new_id] == [1, 2, 3, 4]
    assert len(after) == 5
    original, changed = native(before), native({**before, "bands": after})
    for load in [0, .1, at / 100, (at + .01) / 100, .25, .5, .75, 1, 1.5, 10]:
        for special in (False, True):
            for forced in (False, True):
                assert bands.evaluate(changed, load, special, forced) == pytest.approx(
                    bands.evaluate(original, load, special, forced))


@pytest.mark.parametrize("identity,at", [
    (1, 0), (1, 25), (2, 25), (2, 50), (4, 100),
    (1, True), (1, float("nan")), (1, float("inf")), (1, 12.345),
])
def test_invalid_split_is_nonmutating(identity, at):
    before = bands.project_defaults()["bands"]
    saved = deepcopy(before)
    with pytest.raises(ValueError):
        bands.split(before, identity, at)
    assert before == saved


@pytest.mark.parametrize("identity,neighbour", [(1, 2), (2, 1), (3, 4), (4, 3)])
@pytest.mark.parametrize("keep", ["selected", "neighbour"])
def test_merge_explicitly_selects_properties_and_preserves_coverage(identity, neighbour, keep):
    before = bands.project_defaults()["bands"]
    saved = deepcopy(before)
    after, selected = bands.merge(before, identity, neighbour, keep)
    assert before == saved
    assert selected == neighbour and len(after) == 3
    assert identity not in [b["id"] for b in after]
    survivor = next(b for b in after if b["id"] == neighbour)
    owner = next(b for b in before if b["id"] == (identity if keep == "selected" else neighbour))
    assert {k: survivor[k] for k in ("name", "movement", "recovery")} == {
        k: owner[k] for k in ("name", "movement", "recovery")}
    assert survivor["upper"] == before[max(identity, neighbour) - 1]["upper"]
    assert after[-1]["upper"] is None


@pytest.mark.parametrize("identity,neighbour,keep", [(1, 3, "selected"), (1, 1, "selected"),
                                                    (1, 2, None), (True, 2, "neighbour")])
def test_invalid_merge_is_nonmutating(identity, neighbour, keep):
    value = bands.project_defaults()["bands"]
    saved = deepcopy(value)
    with pytest.raises(ValueError):
        bands.merge(value, identity, neighbour, keep)
    assert value == saved


def test_one_band_and_32_band_limits():
    value = bands.project_defaults()["bands"]
    while len(value) > 1:
        value, _ = bands.merge(value, value[0]["id"], value[1]["id"], "neighbour")
    assert len(value) == 1 and value[0]["upper"] is None
    with pytest.raises(ValueError):
        bands.merge(value, value[0]["id"], value[0]["id"], "selected")
    while len(value) < bands.MAX_BANDS:
        value, _ = bands.split(value, value[-1]["id"], len(value))
    assert len(value) == 32
    assert len(patch.block(native({**config(), "bands": value}))) == patch.EXTENSION_SIZE
    with pytest.raises(ValueError):
        bands.split(value, value[-1]["id"], 33)


@pytest.mark.parametrize("key,value", [
    ("upper", 50), ("upper", None), ("upper", -1), ("upper", float("nan")),
    ("movement", 0), ("movement", 5), ("movement", True),
    ("recovery", -1), ("recovery", 1001), ("recovery", float("inf")),
    ("name", ""), ("name", " "), ("name", "x" * 49), ("name", "a\nb"),
    ("id", 2), ("id", True), ("id", 0),
])
def test_invalid_band_fields_are_rejected(key, value):
    rows = bands.project_defaults()["bands"]
    rows[0][key] = value
    with pytest.raises(ValueError):
        bands.validate_bands(rows)


def test_final_bound_is_protected_and_renaming_has_no_native_effect():
    before = config()
    with pytest.raises(ValueError):
        bands.edit(before["bands"], 4, "upper", 200)
    renamed = bands.edit(before["bands"], 1, "name", "Very light")
    assert native({**before, "bands": renamed}) == native(before)
    assert patch.block(native({**before, "bands": renamed})) == patch.block(native(before))


def test_recovery_can_differ_without_resetting_shared_movement_interpolation():
    value = config()
    value["bands"], new_id = bands.split(value["bands"], 1, 10)
    value["bands"] = bands.edit(value["bands"], new_id, "recovery", 125)
    rules = native(value)
    assert bands.evaluate(rules, .10) == pytest.approx((1, 1, .4))
    assert bands.evaluate(rules, .125) == pytest.approx((1, 1.25, .5))
    assert bands.evaluate(rules, .25) == pytest.approx((1, 1.25, 1))
    assert bands.evaluate(rules, .125, True) == pytest.approx((0, 1, .5))
    assert bands.evaluate(rules, .125, True, True) == pytest.approx((4, .7, .5))
    rules["specialLight"]["enabled"] = False
    assert bands.evaluate(rules, .125, True) == pytest.approx((1, 1.25, .5))


def test_legacy_values_migrate_without_losing_special_or_forced_recovery():
    old = {"lightLimit": 30, "mediumLimit": 60, "heavyLimit": 120,
           "ultralightRecovery": 105, "lightRecovery": 115,
           "mediumRecovery": 95, "heavyRecovery": 60, "overloadedRecovery": 15}
    migrated = bands.legacy_bands(old)
    assert [r["upper"] for r in migrated["bands"]] == [30, 60, 120, None]
    assert [r["recovery"] for r in migrated["bands"]] == [115, 95, 60, 15]
    assert migrated["specialLight"] == {"enabled": True, "recovery": 105}
    assert migrated["forcedRecovery"] == 15


def test_binary_table_domains_and_bounded_roundtrip(monkeypatch):
    value = config()
    value["bands"], _ = bands.split(value["bands"], 1, 10)
    rules = native(value)
    block = patch.block(rules)
    monkeypatch.setattr(patch, "BLOCK_OFFSET", 0)
    assert patch.read_rules(block) == rules
    assert len(block) == 8192
    assert struct.unpack_from("<I", block, 24)[0] == 5
    first = struct.unpack_from("<fI3f", block, patch.TABLE_OFFSET)
    second = struct.unpack_from("<fI3f", block, patch.TABLE_OFFSET + 32)
    assert first == pytest.approx((.1, 1, 1, 0, .25))
    assert second == pytest.approx((.25, 1, 1, 0, .25))
    corrupt = bytearray(block)
    struct.pack_into("<I", corrupt, 20, 8192)
    with pytest.raises(ValueError):
        patch.read_rules(corrupt)


@pytest.fixture(scope="module")
def selector_bridge(tmp_path_factory):
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64") or not shutil.which("gcc"):
        pytest.skip("Independent x64 execution requires Linux x86-64 and GCC")
    path = tmp_path_factory.mktemp("ds1-bands-abi")
    source = path / "adapter.c"
    source.write_text(
        "typedef int (__attribute__((ms_abi)) *tier_fn)(float,float,unsigned,unsigned);\n"
        "typedef float (__attribute__((ms_abi)) *rate_fn)(float,float,unsigned,unsigned);\n"
        "int tier(void*p,float a,float b,unsigned s,unsigned f){return ((tier_fn)p)(a,b,s,f);}\n"
        "float rate(void*p,float a,float b,unsigned s,unsigned f){return ((rate_fn)p)(a,b,s,f);}\n")
    output = path / "adapter.so"
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", str(source), "-o", str(output)], check=True)
    bridge = ctypes.CDLL(str(output))
    for name, result in (("tier", ctypes.c_int), ("rate", ctypes.c_float)):
        function = getattr(bridge, name)
        function.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_uint, ctypes.c_uint]
        function.restype = result
    return bridge


@pytest.mark.parametrize("variant", ["default", "split", "single", "maximum", "special-off"])
def test_compiled_selectors_match_model(selector_bridge, variant):
    import mmap
    value = config()
    if variant in ("split", "special-off"):
        value["bands"], new_id = bands.split(value["bands"], 1, 12.5)
        value["bands"] = bands.edit(value["bands"], new_id, "recovery", 125)
    if variant == "single":
        value["bands"] = [{"id": 1, "name": "Only", "upper": None, "movement": 2, "recovery": 90}]
    if variant == "maximum":
        value["bands"] = [
            {"id": i + 1, "name": str(i + 1), "upper": (i + 1) * 3.125 if i < 31 else None,
             "movement": i % 4 + 1, "recovery": float(i * 25)}
            for i in range(32)]
        # Use supported hundredth-percent inputs at exactly representable binary boundaries.
        for i, row in enumerate(value["bands"][:-1]):
            row["upper"] = float((i + 1) * 3)
    if variant == "special-off":
        value["specialLight"]["enabled"] = False
    rules = native(value)
    image = mmap.mmap(-1, patch.EXTENSION_SIZE, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    try:
        image[:] = patch.block(rules)
        address = ctypes.addressof(ctypes.c_char.from_buffer(image))
        loads = [i / 8 for i in range(1201)]
        loads += [r["upper"] for r in value["bands"] if r["upper"] is not None]
        for weight in loads:
            # Model selection uses the same representable f32 ratio as native SSE.
            ratio = ctypes.c_float(ctypes.c_float(weight).value / 100).value
            runtime = bands.runtime_rows(rules["bands"])
            selected = next((r for r in runtime if ratio <= ctypes.c_float(r[0]).value), runtime[-1])
            for special in (0, 1):
                for forced in (0, 1):
                    profile, recovery = selected[1:3]
                    if forced:
                        profile, recovery = 4, rules["forcedRecovery"] / 100
                    elif special and profile == 1 and rules["specialLight"]["enabled"]:
                        profile, recovery = 0, rules["specialLight"]["recovery"] / 100
                    assert selector_bridge.tier(address + patch.CLASSIFIER_OFFSET, weight, 100, special, forced) == profile
                    assert selector_bridge.rate(address + patch.RECOVERY_OFFSET, weight, 100, special, forced) == pytest.approx(recovery)
    finally:
        image.close()


def test_private_image_projection_and_classifier(selector_bridge):
    """Optional private executable check; never launches or redistributes the game."""
    import hashlib
    import mmap
    import os
    from pathlib import Path

    filename = os.environ.get("LEXEDITOR_DS1_NATIVE_EXE")
    if not filename:
        pytest.skip("Private identified executable not supplied")
    original = Path(filename).read_bytes()
    fingerprint = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
    assert len(original) == 50286344
    assert hashlib.sha256(original).hexdigest() == fingerprint
    pe = struct.unpack_from("<I", original, 0x3C)[0]
    optional = pe + 24
    count = struct.unpack_from("<H", original, pe + 6)[0]
    sections = optional + struct.unpack_from("<H", original, pe + 20)[0]
    image_size = struct.unpack_from("<I", original, optional + 56)[0] + patch.EXTENSION_SIZE
    image = mmap.mmap(-1, image_size, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    try:
        address = ctypes.addressof(ctypes.c_char.from_buffer(image))
        def mapped(source):
            for index in range(count):
                _, rva, size, offset = struct.unpack_from("<4I", source, sections + index * 40 + 8)
                image[rva:rva + size] = source[offset:offset + size]
        samples = [(weight / 8, special, forced)
                   for weight in range(1201) for special in (0, 1) for forced in (0, 1)]
        mapped(original)
        reference = [selector_bridge.tier(address + patch.CLASS_RVA, weight, 100, special, forced)
                     for weight, special, forced in samples]
        value = config()
        value["bands"], _ = bands.split(value["bands"], 1, 12.5)
        rules = native(value)
        projected = patch.transform_verified(original, rules)
        assert len(projected) == len(original) + patch.EXTENSION_SIZE
        assert projected[patch.BLOCK_OFFSET + patch.EXTENSION_SIZE:] == original[patch.BLOCK_OFFSET:]
        assert patch.read_rules(projected) == rules
        last = sections + (count - 1) * 40
        allowed_spans = [(optional + 4, 4), (optional + 56, 4), (optional + 144, 4),
                         (last + 8, 4), (last + 16, 4), (patch.CLASS_OFFSET, 5),
                         (patch.FACTOR_OFFSET, len(patch.FACTOR)),
                         (patch.FRACTION_OFFSET, len(patch.FRACTION)), (patch.BASELINE_OFFSET, 4)]
        cursor = 0
        for start, size in sorted(allowed_spans):
            assert projected[cursor:start] == original[cursor:start]
            cursor = start + size
        assert projected[cursor:patch.BLOCK_OFFSET] == original[cursor:patch.BLOCK_OFFSET]
        mapped(projected)
        assert [selector_bridge.tier(address + patch.CLASS_RVA, weight, 100, special, forced)
                for weight, special, forced in samples] == reference
    finally:
        image.close()
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == fingerprint
