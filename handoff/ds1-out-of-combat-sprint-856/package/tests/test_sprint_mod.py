"""Tests for the external sprint mod, never bundled into Lexeditor's own tests."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest
from core import script_mods
from plugins.ds1 import exe_patches, tweak_mods

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from rebuild import rebuild
PATCH = script_mods.import_module(ROOT, "native_patch")
ENTRY = script_mods.import_module(ROOT, "tweak")


@pytest.fixture(scope="session")
def original():
    path = os.environ.get("LEXEDITOR_DS1_NATIVE_EXE")
    if not path:
        pytest.skip("Supply the private executable through LEXEDITOR_DS1_NATIVE_EXE")
    data = Path(path).read_bytes()
    assert len(data) == PATCH.SUPPORTED_SIZE
    assert hashlib.sha256(data).hexdigest() == PATCH.SUPPORTED_SHA256
    return data


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "library"
    folder = root / "out-of-combat-sprint"
    shutil.copytree(ROOT, folder, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    monkeypatch.setenv(script_mods.TRUST_ENV, str(tmp_path / "trust.json"))
    return root, folder


@pytest.fixture
def installation(tmp_path, original, monkeypatch):
    root = tmp_path / "game"
    root.mkdir()
    live = root / exe_patches.EXECUTABLE
    live.write_bytes(original)
    monkeypatch.setattr(tweak_mods, "ensure_game_closed", lambda: None)
    return root, live


def enable(root, folder):
    script_mods.set_trusted(folder, True)
    tweak_mods.save({"out-of-combat-sprint": {"enabled": True}}, root)


def test_package_is_disabled_and_does_not_grant_trust(library):
    root, folder = library
    assert script_mods.trust_state(folder) == "untrusted"
    rows = tweak_mods.tweak_rows(root)
    assert len(rows) == 1 and not rows[0]["enabled"]
    assert rows[0]["error"] == "" and rows[0]["schema"]["fields"] == []
    assert not (folder / "native").exists()


def test_build_is_pure_and_emits_only_the_native_descriptor():
    result = ENTRY.build({}, None)
    assert list(result) == ["native/out-of-combat-sprint.json"]
    assert json.loads(next(iter(result.values()))) == PATCH.specification()
    with pytest.raises(ValueError):
        ENTRY.build({"unsupported": True}, None)


def test_assembly_rebuild_and_relocations():
    if not all(shutil.which(tool) for tool in ("as", "objcopy", "readelf")):
        pytest.skip("GNU binutils is needed for the reproducibility test")
    code, relocations = rebuild(ROOT)
    assert code == PATCH.CODE[:PATCH.CODE_LENGTH]
    assert relocations == list(PATCH.RELOCATIONS)
    assert PATCH.CODE_LENGTH <= PATCH.UNWIND_OFFSET < len(PATCH.CODE)
    assert all(PATCH.CODE[at:at+4] == b"\0"*4 for at, _ in relocations)


def test_unwind_describes_the_actual_prolog():
    assert PATCH.CODE[:13] == bytes.fromhex("5356574154415541564883ec38")
    assert PATCH.CODE[PATCH.UNWIND_OFFSET:] == bytes.fromhex(
        "01 0d 07 00 0d 62 09 e0 07 d0 05 c0 03 70 02 60 01 30 00 00")
    assert PATCH.specification()["islands"][0]["functions"] == [[0, PATCH.CODE_LENGTH, PATCH.UNWIND_OFFSET]]


def test_descriptor_only_redirects_the_sprint_call():
    raw = PATCH.specification()
    assert raw["hooks"] == [{"rva": PATCH.SPRINT_CALL_RVA, "original": "e801990100",
                             "branch": {"opcode": "E8", "island": "sprint", "offset": 0}}]
    assert "rva" not in raw["islands"][0]
    assert "sectionVirtualSize" not in raw
    exe_patches.validate(raw, "Out-of-combat sprint")


def test_projection_preserves_every_other_original_byte(original):
    descriptor = exe_patches.validate(PATCH.specification(), "Out-of-combat sprint")
    after = exe_patches.compose(original, [descriptor])
    pe = exe_patches._Pe(original)
    assert original[pe.offset(PATCH.SPRINT_CALL_RVA, 5):][:5] == PATCH.ORIGINAL_CALL
    allowed = set()
    for at, length in [(pe.size_of_code, 4), (pe.size_of_image, 4), (pe.checksum, 4), (pe.exception, 8), (pe.security, 8), (pe.last["header"]+8, 8), (pe.last["header"]+16, 4), (pe.offset(PATCH.SPRINT_CALL_RVA, 5), 5)]:
        allowed.update(range(at, at+length))
    for start, end in zip([0] + [at+1 for at in sorted(allowed)], sorted(allowed) + [len(original)]):
        assert after[start:end] == original[start:end]
    assert after[pe.offset(PATCH.NATIVE_CHARGE_RVA, 64):][:64] == original[pe.offset(PATCH.NATIVE_CHARGE_RVA, 64):][:64]
    hook = pe.offset(PATCH.SPRINT_CALL_RVA, 5)
    entry = PATCH.SPRINT_CALL_RVA + 5 + struct.unpack_from("<i", after, hook+1)[0]
    placed = pe.last["raw"] + entry - pe.last["rva"]
    relocated = bytearray(PATCH.CODE)
    for at, target in PATCH.RELOCATIONS:
        struct.pack_into("<i", relocated, at, target - entry - at - 4)
    assert after[placed:placed+len(relocated)] == relocated
    table_rva, size = struct.unpack_from("<II", after, pe.exception)
    table_at = pe.last["raw"] + table_rva - pe.last["rva"]
    functions = list(struct.iter_unpack("<III", after[table_at:table_at+size]))
    assert (entry, entry+PATCH.CODE_LENGTH, entry+PATCH.UNWIND_OFFSET) in functions
    assert all(left[1] <= right[0] for left, right in zip(functions, functions[1:]))
    assert exe_patches.compose(original, []) == original


def test_unknown_build_is_refused(original):
    changed = bytearray(original)
    changed[-1] ^= 1
    with pytest.raises(exe_patches.PatchError):
        exe_patches.compose(bytes(changed), [exe_patches.validate(PATCH.specification(), "Sprint")])


def test_neighbor_composition_and_exact_instruction_conflicts(original):
    sprint = exe_patches.validate(PATCH.specification(), "Sprint")
    neighbor = exe_patches.validate({"version": 1, "islands": [{"name": "neighbor", "code": "c3"}]}, "Neighbor")
    solo = exe_patches.compose(original, [sprint])
    first = exe_patches.compose(original, [neighbor, sprint])
    second = exe_patches.compose(original, [sprint, neighbor])
    pe = exe_patches._Pe(original)
    at = pe.offset(PATCH.SPRINT_CALL_RVA, 5)
    assert first[at:at+5] != solo[at:at+5]
    assert second[at:at+5] == solo[at:at+5]
    with pytest.raises(exe_patches.PatchError, match="both patch"):
        exe_patches.compose(original, [sprint, exe_patches.validate(PATCH.specification(), "Conflicting mod")])


def test_disabled_does_not_build_or_modify_executable(library, installation, original):
    root, folder = library
    game, live = installation
    status = tweak_mods.apply(game, root)
    assert status["state"] == "vanilla"
    assert live.read_bytes() == original
    assert not (folder / "native").exists()
    assert sorted(p.name for p in game.iterdir()) == sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE])


def test_untrusted_enabled_mod_is_refused(library, installation, original):
    root, folder = library
    game, live = installation
    tweak_mods.save({"out-of-combat-sprint": {"enabled": True}}, root)
    with pytest.raises(tweak_mods.TweakError, match="untrusted"):
        tweak_mods.apply(game, root)
    assert live.read_bytes() == original
    assert not (folder / "native").exists()


def test_apply_disable_and_reapply_restore_exact_original(library, installation, original):
    root, folder = library
    game, live = installation
    enable(root, folder)
    result = tweak_mods.apply(game, root)
    assert result["state"] == "tweaked" and result["applied"] == ["Out-of-combat sprint"]
    assert (game / tweak_mods.BACKUP_FILE).read_bytes() == original
    assert live.read_bytes() == exe_patches.compose(original, [exe_patches.validate(PATCH.specification(), "Out-of-combat sprint")])
    assert list((folder / "native").iterdir()) == [folder / "native/out-of-combat-sprint.json"]
    tweak_mods.save({"out-of-combat-sprint": {"enabled": False}}, root)
    assert tweak_mods.apply(game, root)["state"] == "vanilla"
    assert live.read_bytes() == original


def test_restore_does_not_clear_enable_switch(library, installation, original):
    root, folder = library
    game, live = installation
    enable(root, folder)
    tweak_mods.apply(game, root)
    assert tweak_mods.restore(game, root)["state"] == "vanilla"
    assert live.read_bytes() == original
    assert tweak_mods.tweak_rows(root)[0]["enabled"] is True


def test_script_change_revokes_trust(library, installation, original):
    root, folder = library
    game, live = installation
    enable(root, folder)
    with (folder / "script/tweak.py").open("a", encoding="utf-8") as stream:
        stream.write("\n# Changed script.\n")
    assert script_mods.trust_state(folder) == "changed"
    with pytest.raises(tweak_mods.TweakError, match="changed"):
        tweak_mods.apply(game, root)
    assert live.read_bytes() == original


def test_foreign_executable_is_not_overwritten(library, installation):
    root, folder = library
    game, live = installation
    enable(root, folder)
    tweak_mods.apply(game, root)
    modified = bytearray(live.read_bytes())
    modified[0x1000] ^= 1
    live.write_bytes(modified)
    for action in (tweak_mods.apply, tweak_mods.restore):
        with pytest.raises(tweak_mods.TweakError, match="outside Lexeditor"):
            action(game, root)
        assert live.read_bytes() == modified


def test_interrupted_apply_can_be_restored(library, installation, original, monkeypatch):
    root, folder = library
    game, live = installation
    enable(root, folder)
    finish = tweak_mods._finish_manifest
    def interrupted(*args, **kwargs):
        raise OSError("Simulated final journal failure")
    monkeypatch.setattr(tweak_mods, "_finish_manifest", interrupted)
    with pytest.raises(OSError, match="Simulated"):
        tweak_mods.apply(game, root)
    assert tweak_mods.status(game, root)["pendingRecovery"]
    monkeypatch.setattr(tweak_mods, "_finish_manifest", finish)
    assert tweak_mods.restore(game, root)["state"] == "vanilla"
    assert live.read_bytes() == original


def test_native_code_with_inspected_getters(original, tmp_path):
    if sys.platform != "linux" or not shutil.which("gcc"):
        pytest.skip("The isolated native harness requires Linux x86-64 and GCC")
    result = subprocess.run([sys.executable, "-S", str(ROOT / "tests/native_cases.py")],
                            check=True, capture_output=True, text=True, timeout=30)
    evidence = json.loads(result.stdout)
    assert evidence["casesPerAddress"] == 47
    assert evidence["individualCalls"] == 156
    assert evidence["nativeGetters"] and evidence["writerIsSpy"]
