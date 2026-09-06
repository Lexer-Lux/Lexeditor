"""Read-only native FF8 battle regressions; never launches or modifies the game.

Install pefile and unicorn, then run:
  python tools/verify_ff8_native_battle_batch.py --exe "D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/FF8_EN.exe"
The executable stays local. Synthetic model/task/GF records replace live captures.
Rendering and model file I/O are observed, not performed; this is not visual acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct

EXPECTED_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
STACK, STOP, TEMP = 0x2908000, 0x2800000, 0x2801000
MODEL, MODEL_SIZE = 0x1D972C0, 0x9C


def verify(exe: Path) -> None:
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EAX,
                                  UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_ESI,
                                  UC_X86_REG_EDI)
    raw = exe.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Unsupported executable hash; no native addresses were executed")
    pe = pefile.PE(data=raw)
    image = pe.get_memory_mapped_image()

    def machine():
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x2600000)
        u.mem_write(0x400000, image)
        # These fixture addresses overlap the mapped .bind section. Explicitly
        # initialize them; executable bytes are not valid zeroed task records.
        u.mem_write(STOP, bytes(0x10000))
        return u

    def read(u, a, fmt="I"):
        return struct.unpack("<" + fmt, u.mem_read(a, struct.calcsize("<" + fmt)))[0]

    def write(u, a, value, fmt="I"):
        u.mem_write(a, struct.pack("<" + fmt, value))

    def call(u, address, *values):
        u.mem_write(STACK, struct.pack("<" + "I" * (len(values) + 1), STOP, *values))
        u.reg_write(UC_X86_REG_ESP, STACK)
        u.emu_start(address, STOP, count=200000)
        assert u.reg_read(UC_X86_REG_EIP) == STOP, f"Instruction budget exhausted at {address:08X}"

    def ret(u, value=0):
        sp = u.reg_read(UC_X86_REG_ESP)
        u.reg_write(UC_X86_REG_EAX, value)
        u.reg_write(UC_X86_REG_EIP, read(u, sp))
        u.reg_write(UC_X86_REG_ESP, sp + 4)

    for address, target in ((0x4B17D5, 0x4B0F10), (0x4B1100, 0x4A7210), (0x4B127B, 0x4A7210)):
        assert pe.get_data(address - 0x400000, 5) == b'\xe8' + struct.pack('<i', target - address - 5)
    assert pe.get_data(0x103190, 10) == bytes.fromhex('8B 44 24 04 56 BA 01 00 00 00')
    assert pe.get_data(0x1026CD, 6) == bytes.fromhex('66 8B 0E F6 C1 01')
    assert pe.get_data(0xB0F80, 7) == bytes.fromhex('66 C7 44 24 22 0F 00')

    for slot in range(3):
        u = machine()
        u.mem_write(MODEL, bytes(MODEL_SIZE * 3))
        for other in range(3):
            model = MODEL + other * MODEL_SIZE
            write(u, model, 3, "H")
            write(u, model + 4, other, "B")
            write(u, model + 0x88, TEMP + 0x4000 + other * 0x100)
        snapshots = [bytes(u.mem_read(MODEL + i * MODEL_SIZE, MODEL_SIZE)) for i in range(3)]
        event, task, model_task = TEMP, TEMP + 0x100, TEMP + 0x200
        write(u, task + 0x10, event)
        write(u, event + 8, slot, "H")
        write(u, event + 10, 4 + slot, "H")
        calls = []

        def observe_model(uc, address, _size, _data):
            if address in (0x507080, 0x507070, 0x509C80):
                sp = uc.reg_read(UC_X86_REG_ESP)
                calls.append((address, tuple(read(uc, sp + i * 4) for i in range(1, 4))))
                # File loading/polling and unrelated animation updates only.
                ret(uc)
        u.hook_add(UC_HOOK_CODE, observe_model)
        for _ in range(8):
            call(u, 0x502670, task)
        assert read(u, task + 0xD, "B") == 0 and not calls
        # Regression reproduction: the old extension never releases bit 0,
        # so every tick remains at phase zero and no model loading occurs.
        call(u, 0x503190, slot, 22, 1)
        model = MODEL + slot * MODEL_SIZE
        assert read(u, model + 8) & 0x400000
        write(u, model_task + 0xC, model)
        call(u, 0x502AB0, model_task)  # Includes the actual native resource release.
        assert read(u, model, "H") == 0
        call(u, 0x502670, task)
        call(u, 0x502670, task)
        assert read(u, event + 1, "B") == 0xFF
        assert [params[0] for address, params in calls if address == 0x507080] == [4 + slot, 0x1004 + slot]
        for other in range(3):
            if other != slot:
                assert bytes(u.mem_read(MODEL + other * MODEL_SIZE, MODEL_SIZE)) == snapshots[other]
        print(f"PASS slot {slot}: old load stalls; native retirement unblocks model and weapon loading; other slots unchanged")

    # Execute native summon initialization and HUD update, using every GF ID
    # in every participant slot with distinct saved/current/max values.
    for slot in range(3):
        for gf in range(16):
            u = machine()
            stats = 0x1CFF000 + slot * 0x1D0
            saved = 0x1CFDCBA + gf * 0x44
            maximum = 2000 + gf * 30 + slot
            write(u, saved, 1700 + gf, "H")
            write(u, 0x1CFF61A + gf * 0xC, maximum, "H")
            u.reg_write(UC_X86_REG_EBX, gf + 0x40)
            u.reg_write(UC_X86_REG_ESI, stats)
            u.reg_write(UC_X86_REG_EDI, slot * 0xD0)
            u.emu_start(0x48D977, 0x48D9C0, count=100)
            assert read(u, stats + 0x18, "H") == 1700 + gf
            assert read(u, stats + 0x1A, "H") == maximum
            assert read(u, stats + 0x1C, "B") & 1
            assert read(u, stats + 0x1D, "B") == 0x40 + gf
            live_hp = 29 + slot + gf
            write(u, stats + 0x18, live_hp, "H")
            row = TEMP + 0x2000
            def hud_stubs(uc, address, _size, _data):
                if address in (0x47E970, 0x4A0F80, 0x4B9C40):
                    ret(uc, TEMP + 0x3000 if address == 0x47E970 else 40 if address == 0x4A0F80 else 0)
            u.hook_add(UC_HOOK_CODE, hud_stubs)
            u.reg_write(UC_X86_REG_ESP, STACK)
            u.reg_write(UC_X86_REG_EBP, row + 0x49)
            u.reg_write(UC_X86_REG_EBX, stats)
            u.reg_write(UC_X86_REG_EAX, 1)
            u.emu_start(0x4B0555, 0x4B05B3, count=20000)
            assert u.reg_read(UC_X86_REG_EIP) == 0x4B05B3
            assert read(u, row + 0x30, "H") == maximum
            assert read(u, row + 0x32, "H") == live_hp
            assert read(u, saved, "H") == 1700 + gf  # Saved HP would be stale.
    print("PASS: all 48 GF/slot pairs use the verified live summon HP and maximum, not stale saved HP")

    for text, expected in ((bytes((3, 0x30, 0)), 0), (bytes((0x50, 0x51, 0x52, 0)), 3)):
        u = machine()
        u.mem_write(0x1CFDC70, text)
        call(u, 0x47EB50, 0)
        assert u.reg_read(UC_X86_REG_EAX) == 0x1CFDC70
        write(u, 0x1D2B0A8, 0.0, "f")
        write(u, 0xB86D34, 0.001, "f")
        write(u, 0x1D2B0D8, 0, "B")
        glyphs = []
        def observe_text(uc, address, _size, _data):
            if address == 0x403E00:
                ret(uc, TEMP + 0x4000)
            elif address == 0x49C8F0:
                sp = uc.reg_read(UC_X86_REG_ESP)
                glyphs.append(read(uc, 0x1D2B0A8, "f"))
                ret(uc, read(uc, sp + 4))
        u.hook_add(UC_HOOK_CODE, observe_text)
        call(u, 0x4A7250, TEMP + 0x1000, TEMP + 0x2000, 38, 32, 0x1CFDC70, 7)
        assert len(glyphs) == expected
        assert all(abs(depth) < 1e-8 for depth in glyphs)
        assert abs(read(u, 0x1D2B0A8, "f") - 0.001) < 1e-6
    print("PASS: native saved name emits glyphs; foreground text advances the native depth before the later panel")
    print("No live game, full encounter, or visual acceptance is claimed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()
    verify(args.exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
