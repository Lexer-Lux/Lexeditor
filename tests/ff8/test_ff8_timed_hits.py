"""Timed Hits and Blocks (#482/#483) under unicorn.

The game applies an ordinary attack's result as the swing starts and shows
it at the visible contact. The patch notes the rolls' thresholds and holds
the result at the swing start, then judges the press and applies the result
at the contact. These tests run each hook the way the game calls it: the
rolls, the held apply (004911BC), and the contact (00506690)."""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import gameplay_settings
from plugins.ff8 import timed_hits as t

unicorn = pytest.importorskip("unicorn")
keystone = pytest.importorskip("keystone")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
CLOCK = 0x00E0F000        # the stand-in timeGetTime returns this dword
SOUNDS = 0x00E0F010       # the stand-in sound call records its argument here
APPLIED = 0x00E0F200      # the stand-in 00494410: call count, then its nine arguments
INPUT_BLOCK = 0x00E0E000
TIME_STUB = 0x00E0D000
STOP = 0x00E0C000         # a return address that halts the emulator
GAME_RANDOM = 0x77        # the stand-in random byte
OK, CRIT, FAIL = 7, 11, 9

APPLY_STUB = f"""
    inc dword ptr [{APPLIED:#x}]
    push esi
    push edi
    lea esi, [esp + 0xc]
    mov edi, {APPLIED + 4:#x}
    mov ecx, 9
copy:
    mov eax, dword ptr [esi]
    mov dword ptr [edi], eax
    add esi, 4
    add edi, 4
    dec ecx
    jnz copy
    pop edi
    pop esi
    ret
"""


def _machine(now: int = 0, *, window=1000, continuous=False, active=True):
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00800000), (0x00E00000, 0x00010000),
                       (0x01D27000, 0x4000), (0x027AB000, 0x3000)):
        emu.mem_map(base, size)
    emu.mem_write(t.CAVE, t.CODE)
    emu.mem_write(t.DATA, t.data_bytes(window, OK, CRIT, FAIL, continuous))
    emu.mem_write(t.ACTIVE, struct.pack("<I", int(active)))
    emu.mem_write(t.TIME_GET_TIME, struct.pack("<I", TIME_STUB))
    emu.mem_write(TIME_STUB, b"\xA1" + struct.pack("<I", CLOCK) + b"\xC3")  # mov eax,[CLOCK]; ret
    emu.mem_write(CLOCK, struct.pack("<I", now))
    # Sound stand-in: append [esp+4] to the SOUNDS list (count first).
    stub = bytes.fromhex("8B 44 24 04 8B 0D") + struct.pack("<I", SOUNDS)
    stub += bytes.fromhex("89 04 8D") + struct.pack("<I", SOUNDS + 4)
    stub += bytes.fromhex("FF 05") + struct.pack("<I", SOUNDS) + b"\xC3"
    emu.mem_write(t.PLAY_SOUND, stub)
    emu.mem_write(t.RANDOM, bytes((0xB8, GAME_RANDOM, 0, 0, 0, 0xC3)))  # mov eax, 0x77; ret
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    emu.mem_write(t.APPLY, bytes(ks.asm(APPLY_STUB, t.APPLY)[0]))
    for halt in (t.INPUT_RESUME, t.GUNBLADE_RESUME, t.ACTION_RESUME, t.ACTION_END_RESUME,
                 t.CONTACT_RESUME, t.START_SEQUENCE, STOP):
        emu.mem_write(halt, b"\xF4")
    return emu


def _sounds(emu):
    count = struct.unpack("<I", emu.mem_read(SOUNDS, 4))[0]
    return list(struct.unpack(f"<{count}I", emu.mem_read(SOUNDS + 4, 4 * count))) if count else []


def _applied(emu):
    count = struct.unpack("<I", emu.mem_read(APPLIED, 4))[0]
    return count, struct.unpack("<9I", emu.mem_read(APPLIED + 4, 36))


def _at(emu, now: int):
    emu.mem_write(CLOCK, struct.pack("<I", now))


def _press(emu, pressed_bits: int = t.SQUARE):
    emu.mem_write(INPUT_BLOCK + 0x10, struct.pack("<HH", 0x1234, pressed_bits))
    esp = STACK + 0x8000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ECX, INPUT_BLOCK)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xBBBBBBBB)
    emu.emu_start(t.CAVE, t.INPUT_RESUME + 1, count=3000)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xBBBBBBBB
    # The replaced instructions still ran: +0x18 is the held word, AX holds it.
    assert struct.unpack("<H", emu.mem_read(INPUT_BLOCK + 0x18, 2))[0] == 0x1234
    assert emu.reg_read(x86.UC_X86_REG_EAX) & 0xFFFF == 0x1234


def _pressed(emu):
    return struct.unpack("<II", emu.mem_read(t.PRESS_TIME, 8))


def _roll(emu, entry: str, attacker: int, target: int, threshold: int) -> tuple[bool, int]:
    """A replaced random byte as 00492BA0/00492B30 call it: (lands, threshold after)."""
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<IIIII", STOP, 0x5E5E5E5E, 0xCAFEF00D, attacker, target))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, threshold)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.reg_write(x86.UC_X86_REG_EBP, 0xEBEBEBEB)
    emu.emu_start(t.ENTRIES[entry], STOP + 1, count=800)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4
    for reg, value in ((x86.UC_X86_REG_EBX, 0xB0B0B0B0), (x86.UC_X86_REG_EDI, 0xD1D1D1D1),
                       (x86.UC_X86_REG_EBP, 0xEBEBEBEB)):
        assert emu.reg_read(reg) == value
    esi = emu.reg_read(x86.UC_X86_REG_ESI)
    roll = emu.reg_read(x86.UC_X86_REG_EAX) & 0xFF
    return esi != 0 and esi >= roll, esi


def _held(emu, attacker: int, target: int, damage: int) -> bool:
    """004911BC: the call to 00494410. True if the result was held."""
    before = _applied(emu)[0]
    esp = STACK + 0x6000
    args = (target, damage, 0x01D27ADE, 0x01D27ADD, attacker, 0x01D27ADC, 0x01D27AF6, 0x01D27AE8, 0)
    emu.mem_write(esp, struct.pack("<10I", STOP, *args))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    for reg, value in ((x86.UC_X86_REG_ESI, 0x51515151), (x86.UC_X86_REG_EDI, 0xD1D1D1D1),
                       (x86.UC_X86_REG_EBX, 0xB0B0B0B0), (x86.UC_X86_REG_EBP, 0xEBEBEBEB)):
        emu.reg_write(reg, value)
    emu.emu_start(t.ENTRIES["defer"], STOP + 1, count=800)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4
    for reg, value in ((x86.UC_X86_REG_ESI, 0x51515151), (x86.UC_X86_REG_EDI, 0xD1D1D1D1),
                       (x86.UC_X86_REG_EBX, 0xB0B0B0B0), (x86.UC_X86_REG_EBP, 0xEBEBEBEB)):
        assert emu.reg_read(reg) == value
    return _applied(emu)[0] == before


SECOND_EFFECT = bytes(range(0xA0, 0xAC))


def _record(index: int) -> int:
    return t.RECORDS + index * t.RECORD_SIZE


def _swing(emu, attacker, target, *, damage=1000, hit=191, crit=128, auto=False):
    """The swing start: the rolls, the result block, the held apply and the record 0048EF80 writes."""
    index = emu.mem_read(t.RECORD_COUNT, 1)[0]
    if auto:
        esp = STACK + 0x6000
        emu.mem_write(esp, struct.pack("<III", STOP, attacker, target))
        emu.reg_write(x86.UC_X86_REG_ESP, esp)
        emu.emu_start(t.ENTRIES["auto"], STOP + 1, count=200)
        assert emu.reg_read(x86.UC_X86_REG_EAX) == 1
    else:
        lands, _ = _roll(emu, "hit_roll", attacker, target, hit)
        assert lands, "the swing always lands; the press decides at contact"
    crits, _ = _roll(emu, "crit_roll", attacker, target, crit)
    assert not crits, "no crit at the swing; the press decides at contact"
    block = bytearray(t.RESULT_SIZE)
    block[0] = attacker                                   # 01D27AD8
    block[0xE4 - 0xD8:0xE6 - 0xD8] = struct.pack("<H", damage)
    emu.mem_write(t.RESULT_BLOCK, bytes(block))
    held = _held(emu, attacker, target, damage)
    record = bytearray(t.RECORD_SIZE)
    record[0] = target
    record[6:8] = struct.pack("<H", damage)
    record[0xC:] = SECOND_EFFECT             # what 004911FD applied at the swing
    emu.mem_write(_record(index), bytes(record))
    emu.mem_write(t.RECORD_COUNT, bytes((index + 1,)))
    return index, held


def _contact(emu, index: int):
    """00506690(record): the hit visibly connects. Returns (outcome, damage applied, record)."""
    applied_before = _applied(emu)[0]
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<II", 0xCAFEBABE, _record(index)))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.emu_start(t.ENTRIES["contact"], t.CONTACT_RESUME + 1, count=5000)
    # The replaced instructions ran: push ebx; push esi; mov esi, [esp + 0xc].
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 8
    assert emu.reg_read(x86.UC_X86_REG_ESI) == _record(index)
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xB0B0B0B0
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0xD1D1D1D1
    count, args = _applied(emu)
    record = bytes(emu.mem_read(_record(index), t.RECORD_SIZE))
    flags = record[3]
    shown = struct.unpack_from("<H", record, 6)[0]
    if count == applied_before:
        assert flags & 4 and shown == 0, "a miss shows as a miss"
        return "miss", 0, record
    assert shown == args[1], "the number shows what was applied"
    return ("crit" if flags & 2 else "hit"), args[1], record


def _attack(emu, press_at, contact_at, *, swing_at=None, attacker=1, target=4, **swing):
    swing_at = contact_at - 2400 if swing_at is None else swing_at
    if press_at is not None and press_at < swing_at:
        _at(emu, press_at)
        _press(emu)
    _at(emu, swing_at)
    index, held = _swing(emu, attacker, target, **swing)
    assert held
    if press_at is not None and press_at >= swing_at:
        _at(emu, press_at)
        _press(emu)
    _at(emu, contact_at)
    outcome, damage, _ = _contact(emu, index)
    return outcome, damage


def _block(emu, press_at, contact_at, **swing):
    return _attack(emu, press_at, contact_at, attacker=5, target=0, **swing)


# Lexer's attack example: W 1000 ms, 75% hit chance, 50% crit chance: a press
# in the 750 ms before the hit visibly lands hits, in the last 375 ms it crits.
@pytest.mark.parametrize("lead,verdict,damage,sounds", [
    (0, "crit", 2000, [CRIT]), (370, "crit", 2000, [CRIT]), (380, "hit", 1000, [OK]),
    (740, "hit", 1000, [OK]), (760, "miss", 0, [FAIL]), (None, "miss", 0, [])])
def test_lexers_attack_example_judged_at_contact(lead, verdict, damage, sounds):
    emu = _machine(window=1000)
    press = None if lead is None else 10000 - lead
    assert _attack(emu, press, 10000) == (verdict, damage)
    assert _sounds(emu) == sounds


# Lexer's block example: W 1000 ms, 20% hit, 50% crit: the last 800 ms before
# contact dodges, the ~100 ms before that is a normal hit, earlier crits.
@pytest.mark.parametrize("lead,verdict,damage,sounds", [
    (500, "miss", 0, [CRIT]), (850, "hit", 1000, [OK]), (950, "crit", 2000, [FAIL]),
    (None, "crit", 2000, [])])
def test_lexers_block_example_judged_at_contact(lead, verdict, damage, sounds):
    emu = _machine(window=1000)
    press = None if lead is None else 10000 - lead
    assert _block(emu, press, 10000, hit=51) == (verdict, damage)
    assert _sounds(emu) == sounds


def test_a_press_during_the_swing_counts_and_one_before_it_does_not():
    """Lexer: pressing at the visible hit did nothing; the verdict came at the swing start."""
    emu = _machine(window=1000)
    # During the swing, 300 ms before the visible contact: a hit or better.
    assert _attack(emu, 9700, 10000, swing_at=7600)[0] in ("hit", "crit")
    # Before the swing starts: the action start clears it; the attack misses.
    emu = _machine(window=1000)
    _at(emu, 7000)
    _press(emu)
    _action(emu, 7500)
    assert _attack(emu, None, 10000, swing_at=7600) == ("miss", 0)


def test_the_hit_is_held_at_the_swing_and_applied_at_contact():
    emu = _machine(window=1000)
    _at(emu, 7600)
    index, held = _swing(emu, 1, 4, damage=321)
    assert held and _applied(emu)[0] == 0, "nothing reaches 00494410 at the swing"
    _at(emu, 9900)
    _press(emu)
    _at(emu, 10000)
    outcome, damage, _ = _contact(emu, index)
    count, args = _applied(emu)
    assert count == 1 and args[0] == 4 and args[4] == 1, "target and attacker as the game passes them"
    assert args[1] == damage == (642 if outcome == "crit" else 321)
    record = bytes(emu.mem_read(_record(index), t.RECORD_SIZE))
    assert record[0xC:] == SECOND_EFFECT, "the second effect stays as the game recorded it"
    assert args[2:4] == (0x01D27ADE, 0x01D27ADD) and args[5:] == (0x01D27ADC, 0x01D27AF6, 0x01D27AE8, 0)


def test_a_miss_applies_nothing():
    emu = _machine(window=1000)
    assert _attack(emu, None, 10000) == ("miss", 0)
    assert _applied(emu)[0] == 0


def test_a_crit_keeps_to_the_damage_limit():
    emu = _machine(window=1000)
    assert _attack(emu, 10000, 10000, damage=8000) == ("crit", 9999)
    emu = _machine(window=1000)
    assert _attack(emu, 10000, 10000, damage=12000) == ("crit", 24000), "the damage limit was lifted"


def test_untimed_hits_are_applied_at_once():
    emu = _machine()
    # Party on party, enemy on enemy: no roll is noted, the call goes through.
    assert not _held(emu, 0, 1, 50)
    assert not _held(emu, 4, 6, 50)
    # A spell reaches 00494410 without a noted roll: applied at once too.
    assert not _held(emu, 1, 4, 50)
    assert _applied(emu)[0] == 3


def test_rolls_between_untimed_pairs_keep_the_games_random_byte():
    emu = _machine()
    for entry in ("hit_roll", "crit_roll"):
        for attacker, target in ((0, 1), (4, 6)):
            esp = STACK + 0x6000
            emu.mem_write(esp, struct.pack("<IIIII", STOP, 0, 0, attacker, target))
            emu.reg_write(x86.UC_X86_REG_ESP, esp)
            emu.reg_write(x86.UC_X86_REG_ESI, 200)
            emu.emu_start(t.ENTRIES[entry], STOP + 1, count=100)
            assert emu.reg_read(x86.UC_X86_REG_EAX) == GAME_RANDOM
            assert emu.reg_read(x86.UC_X86_REG_ESI) == 200


def test_a_0_percent_hit_keeps_the_games_miss():
    emu = _machine()
    assert _roll(emu, "hit_roll", 1, 4, 0) == (False, 0)
    assert not _held(emu, 1, 4, 50), "nothing noted, so nothing held"


def test_the_hit_window_follows_the_noted_hit_chance():
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 410, 10000, hit=102)[0] == "miss"   # 40%: 400 ms
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 390, 10000, hit=102)[0] == "hit"
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 990, 10000, hit=600)[0] == "hit", "above 100% is the whole window"
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 990, 10000, auto=True)[0] == "hit", "an automatic hit is 100%"


def test_a_crit_chance_of_zero_never_crits():
    emu = _machine(window=1000)
    assert _attack(emu, 10000, 10000, crit=0)[0] == "hit"


def test_a_block_against_an_attack_that_cannot_crit_is_a_normal_hit_at_worst():
    emu = _machine(window=1000)
    assert _block(emu, None, 10000, hit=51, crit=0) == ("hit", 1000)


def test_a_contact_without_a_held_result_is_left_alone():
    emu = _machine()
    record = bytearray(t.RECORD_SIZE)
    record[0], record[3], record[6] = 4, 0x10, 0x44
    emu.mem_write(_record(3), bytes(record))
    _contact_raw = bytes(record)
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<II", 0xCAFEBABE, _record(3)))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.emu_start(t.ENTRIES["contact"], t.CONTACT_RESUME + 1, count=500)
    assert bytes(emu.mem_read(_record(3), t.RECORD_SIZE)) == _contact_raw
    assert _applied(emu)[0] == 0


def test_a_held_result_is_used_once():
    emu = _machine(window=1000)
    _at(emu, 7600)
    index, _ = _swing(emu, 1, 4)
    _at(emu, 10000)
    assert _contact(emu, index)[0] == "miss"
    record = bytes(emu.mem_read(_record(index), t.RECORD_SIZE))
    _contact(emu, index) if False else None
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<II", 0xCAFEBABE, _record(index)))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.emu_start(t.ENTRIES["contact"], t.CONTACT_RESUME + 1, count=500)
    assert bytes(emu.mem_read(_record(index), t.RECORD_SIZE)) == record, "0050A6C0 shows it again unchanged"


def test_every_hit_of_a_multi_hit_attack_is_judged_at_its_own_contact():
    emu = _machine(window=1000)
    _at(emu, 7000)
    first, _ = _swing(emu, 2, 3)
    second, _ = _swing(emu, 2, 3)
    _at(emu, 9900)
    _press(emu)
    _at(emu, 10000)
    assert _contact(emu, first)[0] in ("hit", "crit")
    _at(emu, 10250)
    _press(emu)                            # the try came back with the first hit
    _at(emu, 10300)
    assert _contact(emu, second)[0] in ("hit", "crit")
    assert len(_sounds(emu)) == 2


@pytest.mark.parametrize("lead,verdict,dealt", [(0, "crit", 2000), (187, "crit", 1502),
                                                (562, "hit", 500), (748, "hit", 2)])
def test_continuous_grading_on_an_attack(lead, verdict, dealt):
    emu = _machine(window=1000, continuous=True)
    assert _attack(emu, 10000 - lead, 10000) == (verdict, dealt)


@pytest.mark.parametrize("lead,verdict,taken", [(850, "hit", 505), (950, "crit", 1504),
                                                (None, "crit", 2000)])
def test_continuous_grading_on_a_block(lead, verdict, taken):
    emu = _machine(window=1000, continuous=True)
    assert _block(emu, None if lead is None else 10000 - lead, 10000, hit=51) == (verdict, taken)


def test_rolls_inside_00492e10_are_noted_the_same_way():
    emu = _machine()
    esp = STACK + 0x6000
    for entry, threshold in (("e10_hit_roll", 191), ("e10_crit_roll", 128)):
        emu.mem_write(esp, struct.pack("<I", STOP))
        emu.reg_write(x86.UC_X86_REG_ESP, esp)
        emu.reg_write(x86.UC_X86_REG_ESI, 2 * 0xD0)
        emu.reg_write(x86.UC_X86_REG_EBP, 5 * 0xD0)
        emu.reg_write(x86.UC_X86_REG_EDI, threshold)
        emu.emu_start(t.ENTRIES[entry], 0, count=300)
    assert struct.unpack("<III", emu.mem_read(t.THR_HIT, 12)) == (191, 128, 1)
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0, "no crit at the swing"
    emu.mem_write(esp, struct.pack("<I", STOP))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EDI, 40)
    emu.emu_start(t.ENTRIES["e10_auto_crit"], 0, count=300)
    assert struct.unpack("<III", emu.mem_read(t.THR_HIT, 12)) == (255, 40, 1)


def _gunblade(emu, *, landing=True, luck=30):
    emu.mem_write(t.HIT_COUNTER, struct.pack("<H", 1 if landing else 0))
    emu.mem_write(t.PARTICIPANTS + t.LUCK, bytes((luck,)))
    emu.mem_write(t.CRIT_BONUS, b"\x00")
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<III", 0xEBEBEBEB, 0xCAFEF00D, 0))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBP, 4)
    emu.reg_write(x86.UC_X86_REG_EDX, 12)
    emu.emu_start(t.ENTRIES["gunblade"], 0, count=500)
    assert emu.reg_read(x86.UC_X86_REG_EIP) - 1 == t.GUNBLADE_RESUME, "Squall never misses at the swing"
    assert emu.reg_read(x86.UC_X86_REG_EAX) == 4 + 4 * 12


def test_squall_is_judged_at_contact_like_everyone():
    emu = _machine(window=1000)
    _gunblade(emu)
    assert struct.unpack("<III", emu.mem_read(t.THR_HIT, 12)) == (255, 29, 1)
    emu = _machine(window=1000)
    _gunblade(emu, landing=False)
    assert struct.unpack("<I", emu.mem_read(t.THR_VALID, 4))[0] == 0, "his no-damage call is not held"


def test_square_counts_only_while_an_action_plays():
    """Lexer: outside an attack the code should not fire at all."""
    emu = _machine(window=1000, active=False)
    _at(emu, 1000)
    _press(emu)
    _at(emu, 1050)
    _press(emu)
    assert _pressed(emu) == (0, 0) and _sounds(emu) == []
    _action(emu, 2000)
    assert _active(emu) == 1
    _removed(emu, 10)
    assert _active(emu) == 1, "a damage message does not end the action"
    _removed(emu, t.ACTION_MESSAGE)
    assert _active(emu) == 0


def test_an_action_start_clears_a_leftover_press_and_roll_silently():
    emu = _machine(window=1000)
    _at(emu, 1000)
    _press(emu)
    emu.mem_write(t.THR_VALID, struct.pack("<I", 1))
    _action(emu, 3000)
    assert _pressed(emu)[1] == 0 and _sounds(emu) == []
    assert struct.unpack("<I", emu.mem_read(t.THR_VALID, 4))[0] == 0


def test_one_try_per_hit_and_a_fumble_sounds_once():
    emu = _machine(window=1000)
    _at(emu, 7000)
    index, _ = _swing(emu, 1, 4)
    _at(emu, 8000)
    _press(emu)
    _at(emu, 8100)
    _press(emu)
    assert _sounds(emu) == [FAIL], "the second try fails at once"
    for now in range(8200, 9900, 300):
        _at(emu, now)
        _press(emu)
    _at(emu, 10000)
    assert _contact(emu, index)[0] == "miss"
    assert _sounds(emu) == [FAIL], "the contact adds nothing"


def _action(emu, now: int):
    """0050A790: the scheduler starts an action's animation task."""
    _at(emu, now)
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<II", 0xCAFEF00D, 0x00AB0000))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, 0x5E5E5E5E)
    emu.emu_start(t.ENTRIES["action"], t.ACTION_RESUME + 1, count=200)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 4
    assert emu.reg_read(x86.UC_X86_REG_ESI) == 0x00AB0000


def _removed(emu, message_type: int):
    """00500D51: the scheduler removes a finished message."""
    message = STACK + 0x5000
    emu.mem_write(message, struct.pack("<BBH", 3, 0xFF, message_type))
    esp = STACK + 0x6000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, message)
    emu.emu_start(t.ENTRIES["action_end"], t.ACTION_END_RESUME + 1, count=500)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 4
    assert struct.unpack("<I", emu.mem_read(esp - 4, 4))[0] == 0x01D96D68


def _active(emu):
    return struct.unpack("<I", emu.mem_read(t.ACTIVE, 4))[0]


def test_square_records_the_time_and_other_buttons_do_not():
    emu = _machine(1000)
    _swing(emu, 1, 4)
    _press(emu, 0x08 | 0x20)
    assert _pressed(emu) == (0, 0)
    _press(emu, 0x80 | 0x20)
    assert _pressed(emu) == (1000, 1)


def test_square_does_nothing_without_a_timed_hit_waiting():
    """Lexer: a press during the battle's opening dialogue buzzed."""
    emu = _machine(1000)                  # an action plays, but nothing is held
    for now in (1000, 1050, 1100):
        _at(emu, now)
        _press(emu)
    assert _pressed(emu) == (0, 0) and _sounds(emu) == []


def test_an_action_end_drops_what_it_held():
    emu = _machine(1000)
    index, _ = _swing(emu, 1, 4)
    _removed(emu, t.ACTION_MESSAGE)
    assert emu.mem_read(t.SLOTS + index * t.SLOT_SIZE, 1)[0] == 0


def test_hext_and_hooks():
    assert t.build_hext(False) == ""
    text = t.build_hext(True, window_ms=1000, success_sound=12, crit_sound=13, failure_sound=34,
                        continuous=True)
    assert f"\n{t.DATA:X} = {t.data_bytes(1000, 12, 13, 34, True).hex(' ').upper()}" in text
    for site in (t.INPUT_HOOK, t.ACTION_HOOK, t.ACTION_END_HOOK, t.AUTO_HOOK, t.GUNBLADE_HOOK,
                 t.CONTACT_HOOK):
        assert f"\n{site:X} = E9" in text
    for site in (t.HIT_ROLL_CALL, t.CRIT_ROLL_CALL, t.E10_AUTO_CRIT_CALL, t.E10_HIT_ROLL_CALL,
                 t.E10_CRIT_ROLL_CALL, t.DEFER_CALL):
        assert f"\n{site:X} = E8" in text
    assert "491124 =" not in text and "4922B0 =" not in text
    assert t.CAVE + len(t.CODE) <= t.DATA
    assert len(t.data_bytes(1000, 1, 2, 3)) == t.DATA_SIZE
    for bad in ({"window_ms": 10}, {"window_ms": 2001}, {"success_sound": 0}, {"crit_sound": 0},
                {"failure_sound": True}, {"continuous": 1}):
        with pytest.raises(ValueError):
            t.build_hext(True, **bad)


def test_embedded_code_matches_its_source():
    assert t._assemble() == (t.CODE, t.ENTRIES)


def test_settings_round_trip_and_reach_the_patch(tmp_path):
    from unittest.mock import patch
    project, game, runtime = tmp_path / "mod", tmp_path / "game", tmp_path / "runtime"
    project.mkdir()
    game.mkdir()
    gameplay_settings.initialize_project(project)
    loaded = gameplay_settings.load(project, game)
    assert loaded["timedHits"] is False and loaded["timedHitsWindow"] == t.DEFAULT_WINDOW_MS
    assert loaded["timedHitsContinuous"] is False
    with patch.object(gameplay_settings, "_verify_executable", return_value=game / "FF8_EN.exe"):
        data = {**loaded, "timedHits": True, "timedHitsWindow": 1000, "timedHitsSuccessSound": 40,
                "timedHitsCritSound": 42, "timedHitsFailureSound": 41, "timedHitsContinuous": True}
        gameplay_settings.save(data, game, project, runtime_root=runtime)
        saved = gameplay_settings.load(project, game)
        for key in ("timedHits", "timedHitsWindow", "timedHitsSuccessSound", "timedHitsCritSound",
                    "timedHitsFailureSound", "timedHitsContinuous"):
            assert saved[key] == data[key], key
        patch_text = gameplay_settings.patch_path(project).read_text(encoding="utf-8")
        assert f"{t.DATA:X} = {t.data_bytes(1000, 40, 42, 41, True).hex(' ').upper()}" in patch_text


def _swing_starts(emu, now: int, model: int, sequence: int = 0x0D):
    """0050BB9E: the action task starts the attacker's attack sequence."""
    _at(emu, now)
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<III", 0x0050BBA3, t.MODELS + model * t.MODEL_SIZE, sequence))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.reg_write(x86.UC_X86_REG_ESI, 0x51515151)
    emu.emu_start(t.ENTRIES["swing"], t.START_SEQUENCE + 1, count=300)
    # It went on into 00505C00 with the game's own arguments.
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xB0B0B0B0
    assert emu.reg_read(x86.UC_X86_REG_ESI) == 0x51515151


def _predicted(emu):
    return struct.unpack("<I", emu.mem_read(t.PREDICTED, 4))[0]


def _learned(emu, model, sequence):
    return struct.unpack("<I", emu.mem_read(t.LEARNED + (model * 32 + sequence) * 4, 4))[0]


def _first_swing(emu, *, attacker=1, target=4, model=1):
    """Swing 0 of an attack: held at 7000, the attack sequence at 7300, contact at 9300."""
    _at(emu, 7000)
    index, _ = _swing(emu, attacker, target)
    _swing_starts(emu, 7300, model)
    assert _predicted(emu) == 0, "nothing learned yet"
    _at(emu, 9300)
    _contact(emu, index)
    assert _learned(emu, model, 0x0D) == 2000
    emu.mem_write(t.RECORD_COUNT, b"\x00")
    return index


def test_the_first_swing_teaches_the_contact_delay():
    emu = _machine(window=1000)
    _first_swing(emu)
    _at(emu, 12000)
    index, _ = _swing(emu, 1, 4)
    _swing_starts(emu, 12300, 1)
    assert _predicted(emu) == 14300


def test_a_press_is_heard_at_once_when_the_contact_is_predicted():
    """Lexer: the sound should play the moment you hit the button. every time."""
    emu = _machine(window=1000)
    _first_swing(emu)
    sounds_before = len(_sounds(emu))
    _at(emu, 12000)
    index, _ = _swing(emu, 1, 4)
    _swing_starts(emu, 12300, 1)
    _at(emu, 14000)                       # 300 ms before the predicted contact: a crit
    _press(emu)
    assert _sounds(emu)[sounds_before:] == [CRIT], "heard the moment it is pressed"
    _at(emu, 14100)
    _press(emu)                           # the one try is spent: nothing more
    _at(emu, 14320)                       # the contact comes a little late
    assert _contact(emu, index)[:2] == ("crit", 2000), "the verdict heard is the one applied"
    assert _sounds(emu)[sounds_before:] == [CRIT], "the contact adds no sound"
    assert _learned(emu, 1, 0x0D) == 2020, "each first contact refreshes the delay"


def test_a_predicted_miss_is_heard_at_once_too():
    emu = _machine(window=1000)
    _first_swing(emu)
    sounds_before = len(_sounds(emu))
    _at(emu, 12000)
    index, _ = _swing(emu, 1, 4)
    _swing_starts(emu, 12300, 1)
    _at(emu, 12500)                       # 1800 ms early
    _press(emu)
    assert _sounds(emu)[sounds_before:] == [FAIL]
    _at(emu, 14300)
    assert _contact(emu, index)[:2] == ("miss", 0)


def test_a_press_after_the_predicted_contact_waits_for_the_real_one():
    emu = _machine(window=1000)
    _first_swing(emu)
    sounds_before = len(_sounds(emu))
    _at(emu, 12000)
    index, _ = _swing(emu, 1, 4)
    _swing_starts(emu, 12300, 1)
    _at(emu, 14350)                       # after the prediction, before the contact
    _press(emu)
    assert _sounds(emu)[sounds_before:] == []
    _at(emu, 14400)
    assert _contact(emu, index)[0] == "crit"
    assert _sounds(emu)[sounds_before:] == [CRIT]


def test_a_predicted_block_is_heard_at_once():
    emu = _machine(window=1000)
    _first_swing(emu, attacker=5, target=0, model=5)
    sounds_before = len(_sounds(emu))
    _at(emu, 12000)
    index, _ = _swing(emu, 5, 0, hit=51)
    _swing_starts(emu, 12300, 5)
    _at(emu, 13800)                       # 500 ms before: inside the 800 ms dodge
    _press(emu)
    assert _sounds(emu)[sounds_before:] == [CRIT]
    _at(emu, 14300)
    assert _contact(emu, index)[:2] == ("miss", 0)


def test_an_unknown_model_or_sequence_predicts_nothing():
    emu = _machine(window=1000)
    _first_swing(emu)
    _swing_starts(emu, 12300, 1, sequence=0x40)
    assert _predicted(emu) == 0
    _swing_starts(emu, 12300, 9)
    assert _predicted(emu) == 0


def test_a_new_action_clears_results_left_from_the_last():
    emu = _machine(window=1000)
    _at(emu, 7000)
    first, _ = _swing(emu, 1, 4)
    second, _ = _swing(emu, 1, 4)          # never reached its contact
    emu.mem_write(t.RECORD_COUNT, b"\x00")
    _at(emu, 9000)
    index, _ = _swing(emu, 1, 4)           # the next action's first record
    assert index == 0
    held = [emu.mem_read(t.SLOTS + n * t.SLOT_SIZE, 1)[0] for n in range(3)]
    assert held == [1, 0, 0], "the stale second result is gone"



def _paint(emu, now: int):
    """A battle input frame with nothing pressed; returns the marker's colours."""
    _at(emu, now)
    _press(emu, 0)
    return struct.unpack("<15I", emu.mem_read(t.MARKER_COLOURS, 60))


def _colour(colours):
    """The colour of the brightest corner (brightness 0xFF), as 0xBBGGRR."""
    return colours[1] & 0xFFFFFF


def test_the_marker_is_white_when_nothing_waits():
    emu = _machine()
    colours = _paint(emu, 1000)
    assert _colour(colours) == 0xFEFEFE, "white, at each corner's own brightness"
    assert colours[0] == 0x30545454 and colours[5] == 0x30444444
    assert all(value >> 24 == 0x30 for value in colours)


def test_the_marker_shows_green_blue_and_purple_as_the_contact_nears():
    """Lexer: green when a timed input can be entered, blue when it would succeed,
    purple when perfect. W 1000, 75% hit (749 ms), 50% crit (375 ms)."""
    emu = _machine(window=1000)
    _first_swing(emu)
    _at(emu, 12000)
    _swing(emu, 1, 4)
    assert _colour(_paint(emu, 12100)) == 0x00FE00, "waiting, before the attack sequence"
    _swing_starts(emu, 12300, 1)                        # contact predicted at 14300
    assert _colour(_paint(emu, 13400)) == 0x00FE00      # 900 ms out
    assert _colour(_paint(emu, 13700)) == 0xFE7F00      # 600 ms: a hit
    assert _colour(_paint(emu, 14000)) == 0xFE00B3      # 300 ms: a crit


def test_the_marker_on_a_block_shows_the_dodge_band_as_purple():
    emu = _machine(window=1000)
    _first_swing(emu, attacker=5, target=0, model=5)
    _at(emu, 12000)
    _swing(emu, 5, 0, hit=51)
    _swing_starts(emu, 12300, 5)                        # contact at 14300
    assert _colour(_paint(emu, 13250)) == 0x00FE00      # 1050 ms: outside W
    assert _colour(_paint(emu, 13450)) == 0xFE7F00      # 850 ms: the normal band
    assert _colour(_paint(emu, 13800)) == 0xFE00B3      # 500 ms: the dodge band


def test_the_marker_is_left_alone_when_the_indicator_is_off():
    emu = _machine()
    emu.mem_write(t.INDICATOR, struct.pack("<I", 0))
    emu.mem_write(t.MARKER_COLOURS, t.MARKER_ORIGINAL)
    _paint(emu, 1000)
    assert bytes(emu.mem_read(t.MARKER_COLOURS, 60)) == t.MARKER_ORIGINAL


def _marker_owner(emu):
    """004BB0B5: the marker drawer asks whose turn it is."""
    emu.mem_write(t.MARKER_OWNER, bytes.fromhex("B8 02 00 00 00 C3"))  # the turn: slot 2
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<I", STOP))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, 0x51515151)
    emu.emu_start(t.ENTRIES["marker_owner"], STOP + 1, count=300)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4
    assert emu.reg_read(x86.UC_X86_REG_ESI) == 0x51515151
    return emu.reg_read(x86.UC_X86_REG_EAX)


def test_the_marker_goes_over_whoever_the_waiting_hit_involves():
    """Lexer: how will we do this when non-active characters are getting attacked?"""
    emu = _machine()
    assert _marker_owner(emu) == 2, "nothing waits: the character whose turn it is"
    _swing(emu, 5, 0)                     # an enemy hits party member 0
    assert _marker_owner(emu) == 0
    emu = _machine()
    _swing(emu, 1, 4)                     # party member 1 attacks
    assert _marker_owner(emu) == 1


def test_the_marker_stays_with_the_turn_when_the_indicator_is_off():
    emu = _machine()
    emu.mem_write(t.INDICATOR, struct.pack("<I", 0))
    _swing(emu, 5, 0)
    assert _marker_owner(emu) == 2
