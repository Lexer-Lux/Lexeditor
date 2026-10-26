"""Lexeditor's DS1 loader (dinput8.dll) patches a game in memory, all or nothing.

The shipped DLL must be built from the source beside it (its manifest names
the source's hash). When Zig is available, runtime_loader_harness.c runs the
loader's core against a synthetic image: a function that returns 1 is
redirected into code past the image that returns 42, its unwind entry is
registered, and a patch whose original bytes do not match changes nothing.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from plugins.ds1 import exe_patches, tweak_mods

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "plugins" / "ds1" / "runtime"
IMAGE_SIZE, TIMESTAMP = 0x3000, 0x1234ABCD
# mov eax, 42 ; ret, then an unwind entry for that one-instruction leaf.
RETURNS_42 = bytes.fromhex("B82A000000C3") + b"\0" * 2 + bytes.fromhex("01000000")


def build_module():
    spec = importlib.util.spec_from_file_location("ds1_runtime_build", RUNTIME / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shipped_loader_is_built_from_its_source():
    manifest = json.loads((RUNTIME / "package" / "runtime-manifest.json").read_text(encoding="utf-8"))
    assert manifest["sourceSha256"] == build_module().source_hash(), \
        "Rebuild: python plugins/ds1/runtime/build.py"
    assert tweak_mods.loader_bytes()  # checks the published hash


def test_the_shipped_debug_loader_is_built_from_its_source():
    build = build_module()
    manifest = json.loads((RUNTIME / "package" / "debug" / "runtime-manifest.json").read_text(encoding="utf-8"))
    assert manifest["sourceSha256"] == build.source_hash(build.DEBUG_SOURCES), \
        "Rebuild: python plugins/ds1/runtime/build.py --debug --dearxan FOLDER"
    assert manifest["dearxan"] == build.DEARXAN
    assert tweak_mods.loader_bytes(debug=True)  # checks the published hash


def test_the_debug_loader_leaves_the_game_no_network(tmp_path):
    """A game with Arxan off must never reach other players: once the debug
    loader is in, a name lookup, a connection and a UDP send all fail."""
    import shutil
    try:
        zig = build_module().find_zig(None)
    except SystemExit:
        pytest.skip("Zig is needed to build the test program")
    folder = tmp_path / "game folder"
    folder.mkdir()
    exe = folder / "game.exe"
    subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O1", "-o", str(exe),
                    str(Path(__file__).with_name("runtime_debug_harness.c")), "-lws2_32"], check=True)
    shutil.copy2(RUNTIME / "package" / "debug" / "dinput8.dll", folder / "dinput8.dll")
    out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert out.stdout.strip() == "before=1,1,1 after=0,0,0 loaded=1", out
    log = (folder / "lexeditor-ds1-patch.log").read_text(encoding="utf-8")
    assert "the game has no network access" in log
    assert "a debugger can attach" in log, log


@pytest.mark.parametrize("patch, online", [(b"LXD1PAT\0not for this program", False), (b"", True)])
def test_the_loader_takes_a_patched_game_offline(tmp_path, patch, online):
    """A game whose code a mod changes must not reach FromSoftware's servers:
    any patch at all blocks the network, even one that then fails to apply.
    An empty patch (a menu-layout-only tweak) leaves the game online."""
    import shutil
    try:
        zig = build_module().find_zig(None)
    except SystemExit:
        pytest.skip("Zig is needed to build the test program")
    folder = tmp_path / "game folder"
    folder.mkdir()
    exe = folder / "game.exe"
    subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O1", "-o", str(exe),
                    str(Path(__file__).with_name("runtime_debug_harness.c")), "-lws2_32"], check=True)
    shutil.copy2(RUNTIME / "package" / "dinput8.dll", folder / "dinput8.dll")
    (folder / "lexeditor-ds1-patch.bin").write_bytes(patch)
    out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, cwd=tmp_path)
    after = "1,1,1" if online else "0,0,0"
    assert out.stdout.strip() == f"before=1,1,1 after={after} loaded=1", out
    log = (folder / "lexeditor-ds1-patch.log").read_text(encoding="utf-8")
    assert ("Online play is off" in log) != online, log


def patch_file(original=bytes.fromhex("B801000000"), image_size=IMAGE_SIZE, delay=None):
    block = 0x10000
    hook = bytes((0xE9,)) + struct.pack("<i", block - (0x1000 + 5))
    records = [struct.pack("<III", exe_patches.DELAY, 0, delay)] if delay is not None else []
    records += [
        struct.pack("<III", exe_patches.BLOCK, block, len(RETURNS_42)) + RETURNS_42,
        struct.pack("<III", exe_patches.FUNCTIONS, 0, 1) + struct.pack("<III", block, block + 6, block + 8),
        struct.pack("<III", exe_patches.HOOK, 0x1000, 5) + original + hook,
    ]
    return (exe_patches.RUNTIME_MAGIC + struct.pack("<IIII", exe_patches.RUNTIME_VERSION, image_size,
                                                    TIMESTAMP, len(records)) + b"".join(records))


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("the loader runs on Windows")
    try:
        zig = build_module().find_zig(None)
    except SystemExit:
        pytest.skip("Zig is not installed here; the loader's native check runs where it is")
    exe = tmp_path_factory.mktemp("loader") / "harness.exe"
    subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O1", "-o", str(exe),
                    str(Path(__file__).with_name("runtime_loader_harness.c"))], check=True)
    return exe


def run(harness, tmp_path, data, wait=None, repair=None):
    path = tmp_path / "patch.bin"
    path.write_bytes(data)
    extra = [str(wait)] if wait is not None else []
    extra += [str(repair)] if repair is not None else []
    out = subprocess.run([str(harness), str(path), *extra], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out
    first, second, *rest = out.stdout.strip().splitlines()
    result = {"applied": first.startswith("applied=1"), "result": int(first.rsplit("result=", 1)[1]),
              "message": first.split("message=", 1)[1].rsplit(" result=", 1)[0],
              "unwind": second == "unwind=1"}
    if rest:
        result["repaired"] = int(rest[0].split("=", 1)[1])
    return result


def test_the_loader_redirects_a_function_into_its_code(harness, tmp_path):
    result = run(harness, tmp_path, patch_file())
    assert result["applied"] and result["result"] == 42, result
    assert result["unwind"], "the patch code's unwind entry is registered"


def test_deferred_hooks_are_written_later_by_the_loader(harness, tmp_path):
    """The game crashes when its code differs while it starts up; hooks wait."""
    early = run(harness, tmp_path, patch_file(delay=3000))
    assert early["applied"] and early["result"] == 1 and "follow after" in early["message"], early
    late = run(harness, tmp_path, patch_file(delay=100), wait=1500)
    assert late["applied"] and late["result"] == 42, late


def test_a_hook_the_game_puts_back_is_written_again(harness, tmp_path):
    """DSR restores its guarded stamina code about a minute after the sprint hook."""
    result = run(harness, tmp_path, patch_file(delay=100), wait=800, repair=1500)
    assert result["result"] == 42 and result["repaired"] == 42, result


@pytest.mark.parametrize("case", ["original", "build"])
def test_a_patch_for_other_code_changes_nothing(harness, tmp_path, case):
    data = patch_file(original=bytes.fromhex("B802000000")) if case == "original" else patch_file(image_size=0x4000)
    result = run(harness, tmp_path, data)
    assert not result["applied"] and result["result"] == 1, result
    assert "nothing was changed" in result["message"] or "not the build" in result["message"]
    assert not result["unwind"]


def test_the_shipped_dll_loads_forwards_directinput_and_leaves_a_game_without_patches_alone(harness, tmp_path):
    import shutil
    zig = build_module().find_zig(None)
    folder = tmp_path / "game folder"
    folder.mkdir()
    exe = folder / "game.exe"
    subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O1", "-o", str(exe),
                    str(Path(__file__).with_name("runtime_dll_harness.c")), "-lole32"], check=True)
    shutil.copy2(RUNTIME / "package" / "dinput8.dll", folder / "dinput8.dll")
    out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30, cwd=tmp_path)
    assert out.stdout.strip() == "loaded=1 created=0", out
    assert "No lexeditor-ds1-patch.bin" in (folder / "lexeditor-ds1-patch.log").read_text(encoding="utf-8")

