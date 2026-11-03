"""Band projections share the native composer without owning a second PE layout."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import struct
import subprocess

import pytest

from plugins.ds1 import exe_patches, load_bands, load_bands_patch, stamina_patch
from test_ds1_exe_patches import synthetic, HOOK_A, HOOK_B, CERT


@pytest.fixture
def original(monkeypatch):
    data = bytearray(synthetic())
    # Small, file-backed stand-ins for the four original edit spans.
    sites = {"CLASS": (0x1200, 0x600), "FACTOR": (0x1300, 0x700),
             "FRACTION": (0x1400, 0x800)}
    for name, (rva, offset) in sites.items():
        monkeypatch.setattr(load_bands_patch, name + "_RVA", rva)
        monkeypatch.setattr(load_bands_patch, name + "_OFFSET", offset)
    monkeypatch.setattr(stamina_patch, "BASELINE_RVA", 0x1500)
    monkeypatch.setattr(stamina_patch, "BASELINE_OFFSET", 0x900)
    struct.pack_into("<f", data, 0x900, 45)
    raw = bytes(data)
    for module, size_key, hash_key in (
            (stamina_patch, "ORIGINAL_SIZE", "ORIGINAL_SHA256"),
            (exe_patches, "VANILLA_SIZE", "VANILLA_SHA256")):
        monkeypatch.setattr(module, size_key, len(raw))
        monkeypatch.setattr(module, hash_key, hashlib.sha256(raw).hexdigest())
    return raw


def rules():
    value = load_bands.project_defaults()
    value["bands"], _ = load_bands.split(value["bands"], 1, 12.5)
    value["bands"] = load_bands.edit(value["bands"], 5, "recovery", 120)
    return load_bands.native_projection({"baseRecovery": 70, **value})


def compose(original, *specs):
    return exe_patches.compose(original, [exe_patches.validate(spec, owner)
                                         for owner, spec in specs])


def test_vanilla_projection_is_an_exact_noop(original):
    defaults = load_bands.native_projection({"baseRecovery": 45, **load_bands.project_defaults()})
    spec = load_bands_patch.patch_spec(original, defaults)
    assert not spec["hooks"] and not spec["islands"]
    assert compose(original, ("Rules", spec)) == original


def test_base_only_does_not_install_the_band_selectors(original):
    value = load_bands.native_projection({"baseRecovery": 65, **load_bands.project_defaults()})
    spec = load_bands_patch.patch_spec(original, value)
    assert not spec["islands"] and len(spec["hooks"]) == 1
    output = compose(original, ("Rules", spec))
    assert struct.unpack_from("<f", output, 0x900)[0] == 65
    for offset, length in ((0x600, 5), (0x700, 41), (0x800, 151)):
        assert output[offset:offset + length] == original[offset:offset + length]


@pytest.mark.parametrize("prefix_size", [0, 16, 4096])
def test_band_code_and_inplace_references_relocate_together(original, prefix_size):
    spec = load_bands_patch.patch_spec(original, rules())
    snapshot = deepcopy(spec)
    prefix = {"version": 1, "islands": [{"name": "unrelated", "code": "c3" * prefix_size}]} if prefix_size else {"version": 1}
    output = compose(original, ("Earlier mod", prefix), ("Rules", spec))
    assert spec == snapshot
    image = exe_patches._Pe(output)
    class_rva, class_offset = load_bands_patch.CLASS_RVA, load_bands_patch.CLASS_OFFSET
    branch = class_rva + 5 + struct.unpack_from("<i", output, class_offset + 1)[0]
    block_rva = branch - load_bands_patch.CLASSIFIER_OFFSET
    block_offset = image.offset(block_rva, load_bands_patch.EXTENSION_SIZE)
    assert block_offset >= len(original)
    assert output[block_offset:block_offset + load_bands_patch.EXTENSION_SIZE] == load_bands_patch.block(rules())
    for rva, file_offset, relocations in (
            (load_bands_patch.FACTOR_RVA, load_bands_patch.FACTOR_OFFSET,
             load_bands_patch.FACTOR_ISLAND_RELOCATIONS),
            (load_bands_patch.FRACTION_RVA, load_bands_patch.FRACTION_OFFSET,
             load_bands_patch.FRACTION_ISLAND_RELOCATIONS)):
        for at, target in relocations:
            actual = rva + at + 4 + struct.unpack_from("<i", output, file_offset + at)[0]
            assert actual == block_rva + target
    # No certificate is moved or lost. The shared composer, not this adapter,
    # handles the invalidated directory and one combined exception table.
    assert output[CERT[0]:CERT[0] + CERT[1]] == original[CERT[0]:CERT[0] + CERT[1]]
    assert struct.unpack_from("<f", output, 0x900)[0] == 70


def test_shared_hooks_conflict_before_a_result_is_returned(original):
    spec = load_bands_patch.patch_spec(original, rules())
    other = {"version": 1, "hooks": [{"rva": load_bands_patch.CLASS_RVA,
                                     "original": original[0x600:0x605].hex(),
                                     "bytes": "90" * 5}]}
    with pytest.raises(exe_patches.PatchError, match="both patch"):
        compose(original, ("Rules", spec), ("Other rules", other))


def test_same_display_name_cannot_alias_two_island_addresses(original):
    spec = load_bands_patch.patch_spec(original, rules())
    validated = exe_patches.validate(spec, "Same display name")
    with pytest.raises(exe_patches.PatchError, match="owner and island"):
        exe_patches.compose(original, [validated, validated])


@pytest.mark.parametrize("relocation", [
    {"at": -1, "island": "payload", "offset": 0},
    {"at": True, "island": "payload", "offset": 0},
    {"at": 2, "island": "payload", "offset": 0},
    {"at": 1, "island": "missing", "offset": 0},
    {"at": 1, "island": [], "offset": 0},
    {"at": 1, "island": "payload", "offset": -1},
    {"at": 1, "island": "payload", "offset": True},
    {"at": 1, "island": "payload", "offset": 16},
    {"at": 1, "island": "payload", "offset": 0, "extra": 1},
    None,
])
def test_bad_hook_relocations_are_rejected(relocation):
    spec = {"version": 2, "islands": [{"name": "payload", "code": "c3" * 16}],
            "hooks": [{"rva": HOOK_A, "original": "e800000000", "bytes": "e800000000",
                       "relocations": [relocation]}]}
    with pytest.raises(exe_patches.PatchError):
        exe_patches.validate(spec, "Rules")


def test_overlapping_hook_relocations_and_outside_branches_are_rejected():
    spec = {"version": 2, "islands": [{"name": "payload", "code": "c3" * 16}],
            "hooks": [{"rva": HOOK_B, "original": "90" * 7, "bytes": "90" * 7,
                       "relocations": [{"at": at, "island": "payload", "offset": 0}
                                       for at in (1, 2)]}]}
    with pytest.raises(exe_patches.PatchError, match="overlapping"):
        exe_patches.validate(spec, "Rules")
    for offset in (16, 17, 2**32 - 1):
        spec["hooks"] = [{"rva": HOOK_A, "original": "e800000000",
                          "branch": {"opcode": "E9", "island": "payload", "offset": offset}}]
        with pytest.raises(exe_patches.PatchError, match="branch offset must be"):
            exe_patches.validate(spec, "Rules")


def test_wrong_private_image_never_exports_hook_bytes(original):
    bad = original[:-1] + bytes([original[-1] ^ 1])
    with pytest.raises(ValueError, match="Unsupported"):
        load_bands_patch.patch_spec(bad, rules())


def test_hook_relocations_require_a_new_description_version():
    spec = {"version": 1, "islands": [{"name": "payload", "code": "c3" * 16}],
            "hooks": [{"rva": HOOK_A, "original": "e800000000", "bytes": "e800000000",
                       "relocations": [{"at": 1, "island": "payload", "offset": 0}]}]}
    with pytest.raises(exe_patches.PatchError, match="version 2"):
        exe_patches.validate(spec, "Rules")
    spec["version"] = 2
    assert exe_patches.validate(spec, "Rules")["hooks"][0]["relocations"] == [(1, "payload", 0)]


def test_hook_relocation_offsets_match_the_linker_relocations(tmp_path):
    import platform
    import shutil
    if platform.system() != "Linux" or not all(shutil.which(tool) for tool in ("as", "objdump")):
        pytest.skip("Independent relocation check requires GNU binutils")
    plugin = Path(load_bands_patch.__file__).parent
    obj = tmp_path / "bands.o"
    subprocess.run(["as", "--64", "-o", str(obj), str(plugin / "load_bands.S")], check=True)
    text = subprocess.check_output(["objdump", "-r", str(obj)], text=True)
    symbols = {"bands_recovery": load_bands_patch.RECOVERY_OFFSET, "one": 40,
               "bands_table": load_bands_patch.TABLE_OFFSET, "bands_count": 24}
    for name, expected in (("factor", load_bands_patch.FACTOR_ISLAND_RELOCATIONS),
                           ("fraction", load_bands_patch.FRACTION_ISLAND_RELOCATIONS)):
        section = text.split(f"RELOCATION RECORDS FOR [.text.{name}]:", 1)[1].split("\n\n", 1)[0]
        actual = []
        for line in section.splitlines():
            parts = line.split()
            if len(parts) == 3 and "R_X86_64" in parts[1]:
                symbol, addend = parts[2].split("-", 1)
                if symbol in symbols:
                    assert int(addend, 16) == 4
                    actual.append((int(parts[0], 16), symbols[symbol]))
        assert tuple(actual) == expected
