"""Flying EVA reaches Physical Attack and the gunblade, executed on FF8_EN.exe.

The first Flying EVA patch only reached 00492E10, which FF8's damage switch
uses for attack types 34 and 36. Ordinary Attack (type 1) and Squall's
gunblade (type 10) never went through it, so every melee hit still landed.
This runs the patched native routines in an emulator for flying and grounded
targets and checks the generated Hext for overlapping writes.
"""
from __future__ import annotations

import hashlib
import re
import struct
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "_scratch/gf-spellbooks-test-deps"))
import unicorn  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP  # noqa: E402

from plugins.ff8 import flying_eva, gameplay_settings  # noqa: E402

EXE = Path(r"D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/FF8_EN.exe")
SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
STACK = 0x30F0000
RETURN = 0x30E0000
RNG = 0x0048F020
PARTY, ENEMY = 0, 3            # battle slots
STRIDE = 0xD0
ENEMY_DATA = 0x03100000


def machine(image: bytes, bonus: int | None, *, flying: bool, melee: bool, hit: int, rng: int):
    vm = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    vm.mem_map(0x400000, 0x2600000)
    vm.mem_write(0x400000, image)
    vm.mem_map(0x3000000, 0x200000)
    vm.mem_write(RETURN, b"\xC3")
    if bonus is not None:
        for site, (replacement, _) in flying_eva.PHYSICAL_HOOKS.items():
            vm.mem_write(site, bytes.fromhex(replacement))
        vm.mem_write(flying_eva.PHYSICAL_CAVE, flying_eva.build_physical_payload(bonus))
    # Enemy slot: data pointer chain to the flag byte at +0xF7.
    vm.mem_write(0x1D27B10 + ENEMY * STRIDE, struct.pack("<I", ENEMY_DATA))
    vm.mem_write(ENEMY_DATA, struct.pack("<I", ENEMY_DATA + 0x100))
    vm.mem_write(ENEMY_DATA + 0x100 + 0xF7, bytes([2 if flying else 0]))
    vm.mem_write(0x1D27B8C + PARTY * STRIDE, struct.pack("<I", 0x1000 if melee else 0))
    vm.mem_write(0x1D2A238, bytes([hit]))
    # FF8's RNG answers a fixed roll.
    def rng_hook(uc, address, size, _):
        uc.reg_write(UC_X86_REG_EAX, rng)
        esp = uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(unicorn.x86_const.UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
    vm.hook_add(unicorn.UC_HOOK_CODE, rng_hook, begin=RNG, end=RNG)
    return vm


def call(vm, function: int, *args: int, stop: int = RETURN) -> int:
    frame = struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a) for a in args)
    vm.mem_write(STACK - len(frame), frame)
    vm.reg_write(UC_X86_REG_ESP, STACK - len(frame))
    vm.emu_start(function, stop, count=4000)
    return vm.reg_read(UC_X86_REG_EAX)


def main() -> int:
    data = EXE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA256
    image = pefile.PE(data=data).get_memory_mapped_image()
    base = 0x400000
    for site, (_, original) in flying_eva.PHYSICAL_HOOKS.items():
        expected = bytes.fromhex(original)
        assert image[site - base:site - base + len(expected)] == expected, hex(site)

    # The embedded bytes are the assembly source, with the bonus zeroed.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ff8_flying_physical_asm as source
    except ImportError:
        print("keystone not available: skipped re-assembly")
    else:
        code, _ = source.assemble()
        template = bytearray(code)
        for offset in flying_eva.PHYSICAL_BONUS_OFFSETS:
            assert template[offset] == source.BONUS_MARK
            template[offset] = 0
        assert source.BASE == flying_eva.PHYSICAL_CAVE
        assert bytes(template) == flying_eva.PHYSICAL_TEMPLATE, "PHYSICAL_TEMPLATE is not its source"

    # 255 shortcut: grounded or ranged still lands outright; a melee swing at a
    # flyer has to roll.
    for flying, melee, bypass in ((False, True, 1), (True, False, 1), (True, True, 0)):
        vm = machine(image, 100, flying=flying, melee=melee, hit=255, rng=0)
        assert call(vm, 0x492B00, PARTY, ENEMY) == bypass, (flying, melee)

    # The roll: +100 EVA makes a melee swing at a flyer miss on every roll; the
    # same swing at a grounded enemy is exactly vanilla.
    for rng in (0, 1, 128, 255):
        vm = machine(image, 100, flying=True, melee=True, hit=255, rng=rng)
        assert call(vm, 0x492BA0, PARTY, ENEMY) == 0, rng
        for flying, melee in ((False, True), (True, False)):
            patched = call(machine(image, 100, flying=flying, melee=melee, hit=90, rng=rng), 0x492BA0, PARTY, ENEMY)
            vanilla = call(machine(image, None, flying=flying, melee=melee, hit=90, rng=rng), 0x492BA0, PARTY, ENEMY)
            assert patched == vanilla, (flying, melee, rng)
    # A smaller bonus still lets some swings through.
    landed = sum(call(machine(image, 25, flying=True, melee=True, hit=255, rng=rng), 0x492BA0, PARTY, ENEMY)
                 for rng in range(256))
    assert 0 < landed < 256, landed

    # Gunblade: a flyer with +100 EVA makes Squall's swing return 0 before the
    # damage code; anything else continues into it (0048F530).
    for rng in (0, 200):
        vm = machine(image, 100, flying=True, melee=True, hit=255, rng=rng)
        assert call(vm, 0x48F480, PARTY, ENEMY, 0) == 0
        vm = machine(image, 100, flying=False, melee=True, hit=255, rng=rng)
        call(vm, 0x48F480, PARTY, ENEMY, 0, stop=0x48F530)

    # Nothing in the composed Hext writes over anything else.
    text = gameplay_settings.build_hext(100, single_gf_enabled=True, max_spell_enabled=True,
        max_spell_value=100, flat_stat_abilities_enabled=True, streamlined_draw_enabled=True,
        draw_once_per_enemy=True, better_card_enabled=True, auto_sort=True, auto_sort_magic=True,
        enhanced_ability_menu=True)
    writes = []
    for line in text.splitlines():
        if match := re.fullmatch(r"([0-9A-F]+) = ([0-9A-F ]+)", line):
            begin = int(match[1], 16)
            writes.append((begin, begin + len(bytes.fromhex(match[2]))))
    writes.sort()
    for (a0, a1), (b0, b1) in zip(writes, writes[1:]):
        assert a1 <= b0, f"{a0:X}-{a1:X} overlaps {b0:X}-{b1:X}"
    print("Flying EVA: Physical Attack, the 255 shortcut and the gunblade take the penalty; "
          "grounded and ranged attacks are vanilla; no overlapping writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
