"""Execute only the wrapper and inspected getters in an isolated Linux process.

The real stamina writer is replaced by a test spy. This is NOT gameplay.
Original code is read only from an explicitly supplied fingerprinted executable.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
from core import script_mods
from plugins.ds1 import exe_patches

PATCH = script_mods.import_module(ROOT, "native_patch")
WORLD = 0x1C77E50
TRACE = 0x37F0000
DATA = 0x3800000
LOCAL, ENEMY, OTHER, MANAGER, REGISTRY, AI, VTABLE, MIND, PERCEPTION, PLAYERS, POOL, SLOTS = (
    DATA + index * 0x1000 for index in range(12))
GETTERS = [(0x392B80, 19), (0x5C7370, 16), (0x61BA70, 11),
           (0x61A820, 28), (0x3714B0, 86), (0x33EC30, 12)]

def main():
    if sys.platform != "linux" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("This isolated native harness requires Linux x86-64")
    original = Path(os.environ["LEXEDITOR_DS1_NATIVE_EXE"]).read_bytes()
    if len(original) != PATCH.SUPPORTED_SIZE or hashlib.sha256(original).hexdigest() != PATCH.SUPPORTED_SHA256:
        raise ValueError("The private executable is not the supported original")
    pe = exe_patches._Pe(original)
    memory = mmap.mmap(-1, 0x4000000, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    base = ctypes.addressof(ctypes.c_char.from_buffer(memory))
    def u32(at, value): struct.pack_into("<I", memory, at, value & 0xFFFFFFFF)
    def ptr(at, value): struct.pack_into("<Q", memory, at, 0 if value == 0 else base + value)
    for rva, size in GETTERS:
        at = pe.offset(rva, size)
        memory[rva:rva+size] = original[at:at+size]
    with tempfile.TemporaryDirectory(prefix="lexeditor-sprint-native-") as temporary:
        folder = Path(temporary)
        shared = folder / "bridge.so"
        subprocess.run(["gcc", "-O2", "-shared", "-fPIC", "-o", str(shared), str(ROOT / "tests/bridge.c")], check=True)
        obj, spy = folder / "spy.o", folder / "spy.bin"
        subprocess.run(["as", "--64", "-o", str(obj), str(ROOT / "tests/writer_spy.S")], check=True)
        subprocess.run(["ld", "-Ttext=0x339680", "--defsym=trace=0x37f0000", "--entry=writer_spy", "--oformat=binary", "-o", str(spy), str(obj)], check=True)
        memory[0x339680:0x339680+len(spy.read_bytes())] = spy.read_bytes()
        bridge = ctypes.CDLL(str(shared))
        bridge.invoke.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        bridge.invoke.restype = ctypes.c_size_t
        def reset():
            memory[DATA:DATA+0x10000] = b"\0"*0x10000
            memory[TRACE:TRACE+32] = b"\0"*32
            ptr(WORLD, MANAGER)
            ptr(MANAGER+0x68, LOCAL); ptr(MANAGER+0x10, REGISTRY)
            u32(REGISTRY+0x18, 1)
            u32(LOCAL+0x3e8, 100); u32(ENEMY+0x3e8, 100); u32(OTHER+0x3e8, 100)
            u32(LOCAL+0x3f8, 77)
            u32(MANAGER+0x38, 2); ptr(MANAGER+0x40, PLAYERS); ptr(PLAYERS, LOCAL)
            ptr(MANAGER+0x440, POOL); u32(POOL, 3); ptr(POOL+8, SLOTS)
            ptr(SLOTS, ENEMY); ptr(SLOTS+0x38, LOCAL)
            ptr(ENEMY+0x70, AI); ptr(AI, VTABLE)
            ptr(VTABLE+0xc8, 0x392B80); ptr(AI+0x230, MIND); ptr(MIND+0x30, PERCEPTION)
            u32(PERCEPTION+0xe0, 0); u32(PERCEPTION+0x58, 1)
            ptr(PERCEPTION+0x78, 0x139DB00); u32(PERCEPTION+0x80, 1)
            ptr(PERCEPTION+0x88, SLOTS+0x38)
        cases = []
        def case(name, expected, *changes, actor=LOCAL, delta=-1):
            cases.append((name, expected, changes, actor, delta))
        case("unengaged", False)
        case("alert", False, (PERCEPTION+0xe0, 1))
        case("search", False, (PERCEPTION+0xe0, 2))
        case("battle_local_cached", True, (PERCEPTION+0xe0, 3))
        case("battle_local_handle", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x88, 0, "ptr"))
        case("battle_other_cached", False, (PERCEPTION+0xe0, 3), (SLOTS+0x70, OTHER, "ptr"), (PERCEPTION+0x80, 2), (PERCEPTION+0x88, SLOTS+0x70, "ptr"), (OTHER+0x70, AI+0x400, "ptr"), (AI+0x400, VTABLE+0x200, "ptr"), (VTABLE+0x200+0xc8, 0x391820, "ptr"))
        case("dead_enemy", False, (ENEMY+0x3e8, 0), (PERCEPTION+0xe0, 3))
        case("negative_enemy_health", False, (ENEMY+0x3e8, -1), (PERCEPTION+0xe0, 3))
        case("known_nonbattle_controller", False, (VTABLE+0xc8, 0x391820, "ptr"), (AI+0x230, 0, "ptr"))
        case("other_loaded_player", True, (PLAYERS+0x38, OTHER, "ptr"))
        case("missing_world", True, (WORLD, 0, "ptr"))
        case("nonlocal_actor", True, actor=ENEMY)
        case("null_actor", True, actor=0)
        case("dead_local", True, (LOCAL+0x3e8, 0))
        case("missing_registry", True, (MANAGER+0x10, 0, "ptr"))
        case("oversized_registry", True, (REGISTRY+0x18, 28))
        case("negative_registry", True, (REGISTRY+0x18, -1))
        case("absent_player_pool", True, (MANAGER+0x38, 0))
        case("missing_player_slots", True, (MANAGER+0x40, 0, "ptr"))
        case("oversized_player_pool", True, (MANAGER+0x38, 0x4001))
        case("oversized_actor_pool", True, (POOL, 0x4001))
        case("missing_actor_slots", True, (POOL+8, 0, "ptr"))
        case("empty_actor_pool", False, (POOL, 0))
        case("empty_slot", False, (SLOTS, 0, "ptr"))
        case("missing_ai", True, (ENEMY+0x70, 0, "ptr"))
        case("missing_vtable", True, (AI, 0, "ptr"))
        case("unknown_battle_getter", True, (VTABLE+0xc8, 0x391825, "ptr"))
        case("missing_mind", True, (AI+0x230, 0, "ptr"))
        case("missing_perception", True, (MIND+0x30, 0, "ptr"))
        case("unknown_battle_enum", True, (PERCEPTION+0xe0, 4))
        case("negative_battle_enum", True, (PERCEPTION+0xe0, -1))
        case("noncharacter_target", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x58, 0))
        case("unknown_target_accessor", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x78, VTABLE, "ptr"))
        case("invalid_target_handle", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x80, -1))
        case("empty_cached_target", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x88, SLOTS+0x70, "ptr"))
        case("target_pool_outside_active_registry", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x88, 0, "ptr"), (PERCEPTION+0x80, 3 << 14))
        case("missing_target_pool", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x88, 0, "ptr"), (PERCEPTION+0x80, 2 << 14))
        case("target_slot_outside_pool", True, (PERCEPTION+0xe0, 3), (PERCEPTION+0x88, 0, "ptr"), (PERCEPTION+0x80, 3))
        case("minimum_active_registry", False, (REGISTRY+0x18, 0))
        case("highest_active_pool", True, (REGISTRY+0x18, 27), (MANAGER+0x440, 0, "ptr"), (MANAGER+0x440+28*8, POOL, "ptr"), (PERCEPTION+0xe0, 3))
        case("pool_above_active_count_not_read", False, (REGISTRY+0x18, 0), (MANAGER+0x440, 0, "ptr"), (MANAGER+0x440+2*8, POOL, "ptr"), (PERCEPTION+0xe0, 3))
        for delta in [0, 1, -2, -20, -(1 << 31), (1 << 31)-1]:
            case(f"preserve_delta_{delta}", True, delta=delta)
        executions = []
        for entry in (0x319C000, 0x3208000, 0x3400000):
            code = bytearray(PATCH.CODE)
            for at, target in PATCH.RELOCATIONS:
                struct.pack_into("<i", code, at, target - entry - at - 4)
            memory[entry:entry+len(code)] = code
            for name, expected, changes, actor, delta in cases:
                reset()
                for change in changes:
                    at, value, *kind = change
                    (ptr if kind else u32)(at, value)
                before_stamina = bytes(memory[LOCAL+0x3f8:LOCAL+0x3fc])
                result = bridge.invoke(base+entry, base+actor if actor else None, delta)
                calls = struct.unpack_from("<Q", memory, TRACE)[0]
                assert calls == int(expected), (name, hex(entry), calls, expected)
                assert result == (0x5a if expected else 0), (name, result)
                assert bytes(memory[LOCAL+0x3f8:LOCAL+0x3fc]) == before_stamina, name
                if expected:
                    assert struct.unpack_from("<Q", memory, TRACE+8)[0] == (base+actor if actor else 0), name
                    assert struct.unpack_from("<i", memory, TRACE+16)[0] == delta, name
                    assert struct.unpack_from("<Q", memory, TRACE+24)[0] % 16 == 8, name
                executions.append({"case": name, "entryRva": hex(entry), "charged": expected})
            reset()
            for state, expected in [(0, False), (3, True), (2, False), (3, True), (0, False)]:
                u32(PERCEPTION+0xe0, state)
                memory[TRACE:TRACE+32] = b"\0"*32
                bridge.invoke(base+entry, base+LOCAL, -1)
                assert struct.unpack_from("<Q", memory, TRACE)[0] == int(expected)
            executions.append({"case": "enter_leave_sequence", "entryRva": hex(entry), "ticks": 5})
        print(json.dumps({"casesPerAddress": len(cases), "addresses": 3,
                          "individualCalls": len(cases)*3 + 15,
                          "nativeGetters": True, "writerIsSpy": True,
                          "executions": executions}))
    memory.close()

if __name__ == "__main__":
    main()
