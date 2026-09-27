"""Timed Hits and Blocks (#482/#483) under unicorn: the press recorder, the
hit and crit verdicts that replace the game's rolls for attacks and blocks,
Squall's gunblade landing, and continuous grading."""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import gameplay_settings
from plugins.ff8 import timed_hits as t

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
CLOCK = 0x00E0F000        # the stand-in timeGetTime returns this dword
SOUNDS = 0x00E0F010       # the stand-in sound call records its argument here
INPUT_BLOCK = 0x00E0E000
TIME_STUB = 0x00E0D000
STOP = 0x00E0C000         # a return address that halts the emulator
GAME_RANDOM = 0x77        # the stand-in random byte
OK, CRIT, FAIL = 7, 11, 9


def _machine(now: int = 0, *, window=1000, continuous=False):
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00800000), (0x00E00000, 0x00010000),
                       (0x01D27000, 0x4000), (0x027AB000, 0x2000)):
        emu.mem_map(base, size)
    emu.mem_write(t.CAVE, t.CODE)
    emu.mem_write(t.DATA, t.data_bytes(window, OK, CRIT, FAIL, continuous))
    emu.mem_write(t.TIME_GET_TIME, struct.pack("<I", TIME_STUB))
    emu.mem_write(TIME_STUB, b"\xA1" + struct.pack("<I", CLOCK) + b"\xC3")  # mov eax,[CLOCK]; ret
    emu.mem_write(CLOCK, struct.pack("<I", now))
    # Sound stand-in: append [esp+4] to the SOUNDS list (count first).
    stub = bytes.fromhex("8B 44 24 04 8B 0D") + struct.pack("<I", SOUNDS)
    stub += bytes.fromhex("89 04 8D") + struct.pack("<I", SOUNDS + 4)
    stub += bytes.fromhex("FF 05") + struct.pack("<I", SOUNDS) + b"\xC3"
    emu.mem_write(t.PLAY_SOUND, stub)
    emu.mem_write(t.RANDOM, bytes((0xB8, GAME_RANDOM, 0, 0, 0, 0xC3)))  # mov eax, 0x77; ret
    for halt in (t.INPUT_RESUME, t.HIT_RESUME, t.GUNBLADE_RESUME, t.GUNBLADE_NO_DAMAGE, t.E10_MISS, STOP):
        emu.mem_write(halt, b"\xF4")
    return emu


def _sounds(emu):
    count = struct.unpack("<I", emu.mem_read(SOUNDS, 4))[0]
    return list(struct.unpack(f"<{count}I", emu.mem_read(SOUNDS + 4, 4 * count))) if count else []


def _at(emu, now: int):
    emu.mem_write(CLOCK, struct.pack("<I", now))


def _press(emu, pressed_bits: int = t.SQUARE):
    emu.mem_write(INPUT_BLOCK + 0x10, struct.pack("<HH", 0x1234, pressed_bits))
    esp = STACK + 0x8000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ECX, INPUT_BLOCK)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xBBBBBBBB)
    emu.emu_start(t.CAVE, t.INPUT_RESUME + 1, count=200)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xBBBBBBBB
    # The replaced instructions still ran: +0x18 is the held word, AX holds it.
    assert struct.unpack("<H", emu.mem_read(INPUT_BLOCK + 0x18, 2))[0] == 0x1234
    assert emu.reg_read(x86.UC_X86_REG_EAX) & 0xFFFF == 0x1234


def _pressed(emu):
    return struct.unpack("<II", emu.mem_read(t.PRESS_TIME, 8))


def _roll(emu, entry: str, attacker: int, target: int, threshold: int) -> bool:
    """Call a replaced random byte as 00492BA0/00492B30 do; True if the roll lands."""
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<IIIII", STOP, 0x5E5E5E5E, 0xCAFEF00D, attacker, target))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, threshold)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.reg_write(x86.UC_X86_REG_EBP, 0xEBEBEBEB)
    emu.emu_start(t.ENTRIES[entry], STOP + 1, count=800)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xB0B0B0B0
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0xD1D1D1D1
    assert emu.reg_read(x86.UC_X86_REG_EBP) == 0xEBEBEBEB
    esi = emu.reg_read(x86.UC_X86_REG_ESI)
    roll = emu.reg_read(x86.UC_X86_REG_EAX) & 0xFF
    return esi != 0 and esi >= roll          # the game's own test after the call


def _e10(emu, entry: str, attacker: int, target: int, threshold: int):
    """A replaced random byte inside 00492E10: 'lands', 'fails' or 'miss exit'."""
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<I", STOP))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, attacker * 0xD0)
    emu.reg_write(x86.UC_X86_REG_EBP, target * 0xD0)
    emu.reg_write(x86.UC_X86_REG_EDI, threshold)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.emu_start(t.ENTRIES[entry], 0, count=800)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xB0B0B0B0
    assert emu.reg_read(x86.UC_X86_REG_ESI) == attacker * 0xD0
    if emu.reg_read(x86.UC_X86_REG_EIP) - 1 == t.E10_MISS:
        return "miss exit"
    edi = emu.reg_read(x86.UC_X86_REG_EDI)
    roll = emu.reg_read(x86.UC_X86_REG_EAX) & 0xFF
    return "lands" if edi != 0 and edi >= roll else "fails"


def _auto(emu, attacker: int, target: int) -> int:
    """00492B00's automatic-hit exit."""
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<III", STOP, attacker, target))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.emu_start(t.ENTRIES["auto"], STOP + 1, count=800)
    return emu.reg_read(x86.UC_X86_REG_EAX)


def _damage(emu, damage: int) -> int:
    """The hit's damage through 00491124, where continuous grading scales it."""
    esp = STACK + 0x8000
    emu.mem_write(esp, bytes(0x20))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, damage)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.emu_start(t.ENTRIES["hit"], t.HIT_RESUME + 1, count=500)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0xD1D1D1D1
    return emu.reg_read(x86.UC_X86_REG_ESI)


def _gunblade(emu, attacker: int, target: int, *, landing: bool = True, luck: int = 0, bonus: int = 0):
    """0048F530 inside Squall's gunblade handler: ('hit' or 'miss', crit flag)."""
    emu.mem_write(t.HIT_COUNTER, struct.pack("<H", 1 if landing else 0))
    emu.mem_write(t.PARTICIPANTS + attacker * 0xD0 + t.LUCK, bytes((luck,)))
    emu.mem_write(t.CRIT_BONUS, bytes((bonus,)))
    emu.mem_write(t.CRIT_FLAG, b"\x00")
    emu.mem_write(t.HIT_MARKS, b"\x00")
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<III", 0xEBEBEBEB, 0xCAFEF00D, attacker))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBP, target)
    emu.reg_write(x86.UC_X86_REG_EDX, target * 3)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xB0B0B0B0)
    emu.emu_start(t.ENTRIES["gunblade"], 0, count=1000)
    eip = emu.reg_read(x86.UC_X86_REG_EIP) - 1   # the hlt
    marks = emu.mem_read(t.HIT_MARKS, 1)[0]
    crit = emu.mem_read(t.CRIT_FLAG, 1)[0]
    if eip == t.GUNBLADE_NO_DAMAGE:
        assert emu.reg_read(x86.UC_X86_REG_ESP) == esp and marks & 4
        return "miss", crit
    assert eip == t.GUNBLADE_RESUME, hex(eip)
    # The replaced instructions ran: push ebx; xor ebx, ebx; lea eax, [ebp+edx*4].
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 4
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0
    assert emu.reg_read(x86.UC_X86_REG_EAX) == target + target * 12
    return "hit", crit


def _outcome(emu, attacker, target, press_at, land_at, hit, crit):
    if press_at is not None:
        _at(emu, press_at)
        _press(emu)
    _at(emu, land_at)
    if not _roll(emu, "hit_roll", attacker, target, hit):
        return "miss"
    return "crit" if _roll(emu, "crit_roll", attacker, target, crit) else "hit"


# Lexer's attack example: W 1000 ms, 75% hit chance, 50% crit chance: a press
# in the 750 ms before the hit lands hits, in the last 375 ms it crits.
HIT_75 = 191   # 75% of 255: a 749 ms hit window
CRIT_50 = 128  # 50% of 255: a 375 ms crit window


def _attack(emu, press_at, land_at: int, *, hit=HIT_75, crit=CRIT_50):
    return _outcome(emu, 1, 4, press_at, land_at, hit, crit)


# Lexer's block example: W 1000 ms, 20% hit chance, 50% crit chance: the last
# 800 ms dodges, the 100 ms before that is a normal hit, earlier crits.
HIT_20 = 51    # 20% of 255: an 800 ms dodge band
# CRIT_50 again: a 99 ms normal band, then crits


def _block(emu, press_at, land_at: int, *, hit=HIT_20, crit=CRIT_50):
    return _outcome(emu, 5, 0, press_at, land_at, hit, crit)


@pytest.mark.parametrize("lead,verdict", [(0, "crit"), (370, "crit"), (380, "hit"), (740, "hit"),
                                          (760, "miss"), (1200, "miss")])
def test_lexers_attack_example(lead, verdict):
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - lead, 10000) == verdict
    assert _sounds(emu) == {"crit": [CRIT], "hit": [OK], "miss": [FAIL]}[verdict]


@pytest.mark.parametrize("lead,verdict,sounds", [(0, "miss", [CRIT]), (800, "miss", [CRIT]),
                                                 (850, "hit", [OK]), (899, "hit", [OK]),
                                                 (950, "crit", [FAIL]), (1500, "crit", [FAIL]),
                                                 (None, "crit", [])])
def test_lexers_block_example(lead, verdict, sounds):
    emu = _machine(window=1000)
    assert _block(emu, None if lead is None else 10000 - lead, 10000) == verdict
    assert _sounds(emu) == sounds


def test_a_block_against_an_attack_that_cannot_crit_is_a_normal_hit_at_worst():
    emu = _machine(window=1000)
    assert _block(emu, None, 10000, crit=0) == "hit"
    assert _block(emu, 11000 - 950, 11000, crit=0) == "hit"


def test_a_block_against_a_0_percent_attack_keeps_the_games_miss():
    emu = _machine()
    _press(emu)
    _at(emu, 100)
    assert not _roll(emu, "hit_roll", 5, 0, 0)
    assert _pressed(emu)[1] == 1, "the press is left for a real hit"


def test_an_attack_with_no_press_misses_silently():
    emu = _machine()
    assert _attack(emu, None, 10000) == "miss"
    assert _sounds(emu) == []


def test_the_hit_window_follows_the_hit_chance():
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 410, 10000, hit=102) == "miss"   # 40%: 400 ms
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 390, 10000, hit=102) == "hit"
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 990, 10000, hit=600) == "hit", "above 100% is the whole window"
    emu = _machine(window=1000)
    assert _attack(emu, 10000, 10000, hit=0) == "miss", "0% never hits"


def test_a_crit_chance_of_zero_never_crits():
    emu = _machine(window=1000)
    assert _attack(emu, 10000, 10000, crit=0) == "hit"


def test_the_press_is_used_by_one_hit():
    emu = _machine(window=1000)
    assert _attack(emu, 9900, 10000) == "crit"
    assert _attack(emu, None, 10050) == "miss", "a second hit needs its own press"


def test_party_on_party_and_enemy_on_enemy_keep_the_games_random_byte():
    emu = _machine()
    _press(emu)
    _at(emu, 100)
    esp = STACK + 0x6000
    for entry in ("hit_roll", "crit_roll"):
        for attacker, target in ((0, 1), (4, 6)):
            emu.mem_write(esp, struct.pack("<IIIII", STOP, 0, 0, attacker, target))
            emu.reg_write(x86.UC_X86_REG_ESP, esp)
            emu.reg_write(x86.UC_X86_REG_ESI, 200)
            emu.emu_start(t.ENTRIES[entry], STOP + 1, count=100)
            assert emu.reg_read(x86.UC_X86_REG_EAX) == GAME_RANDOM
            assert emu.reg_read(x86.UC_X86_REG_ESI) == 200
    assert _pressed(emu)[1] == 1


def test_an_enemy_crit_roll_without_a_judged_hit_is_the_games():
    emu = _machine()
    esp = STACK + 0x6000
    emu.mem_write(esp, struct.pack("<IIIII", STOP, 0, 0, 5, 0))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, 200)
    emu.emu_start(t.ENTRIES["crit_roll"], STOP + 1, count=200)
    assert emu.reg_read(x86.UC_X86_REG_EAX) == GAME_RANDOM


def test_an_automatic_hit_is_a_full_window():
    emu = _machine(window=1000)
    _press(emu)
    _at(emu, 900)
    assert _auto(emu, 1, 4) == 1                    # 900 ms of a 1000 ms window
    emu = _machine(window=1000)
    _press(emu)
    _at(emu, 1100)
    assert _auto(emu, 1, 4) == 0                    # too early: the roll after it fails
    assert not _roll(emu, "hit_roll", 1, 4, 255)


def test_an_enemys_automatic_hit_cannot_be_dodged_but_its_crit_is_judged():
    emu = _machine(window=1000)
    _at(emu, 900)
    _press(emu)
    _at(emu, 1000)                                  # 100 ms before
    assert _auto(emu, 5, 0) == 1
    assert not _roll(emu, "crit_roll", 5, 0, CRIT_50), "inside the normal band"
    assert _sounds(emu) == [OK]


def test_types_34_and_36_are_timed_the_same_way():
    """00492E10: the routine Full LUCK Accuracy changes."""
    emu = _machine(window=1000)
    _at(emu, 9700)
    _press(emu)
    _at(emu, 10000)                                   # 300 ms before
    assert _e10(emu, "e10_hit_roll", 2, 5, HIT_75) == "lands"
    assert _e10(emu, "e10_crit_roll", 2, 5, CRIT_50) == "lands"
    _at(emu, 10200)
    _press(emu)
    _at(emu, 11000)                                   # 800 ms before: out of 749
    assert _e10(emu, "e10_hit_roll", 2, 5, HIT_75) == "fails"
    # An enemy's type 34/36 attack is a block like any other.
    _at(emu, 12000)
    _press(emu)
    _at(emu, 12500)                                   # inside the 800 ms dodge band
    assert _e10(emu, "e10_hit_roll", 5, 0, HIT_20) == "fails"
    assert _sounds(emu) == [CRIT, FAIL, CRIT]


def test_the_automatic_hit_in_00492e10_can_miss():
    emu = _machine(window=1000)
    _at(emu, 5000)
    assert _e10(emu, "e10_auto_crit", 0, 3, 40) == "miss exit"   # no press
    _at(emu, 6000)
    _press(emu)
    _at(emu, 6500)                                    # 500 ms of a full 1000
    assert _e10(emu, "e10_auto_crit", 0, 3, 40) == "fails"      # a hit, not a crit
    assert _sounds(emu) == [OK]


def test_squall_misses_without_a_press_and_crits_with_a_late_one():
    emu = _machine(window=1000)
    _at(emu, 5000)
    assert _gunblade(emu, 0, 4) == ("miss", 0)
    # LUCK 30, no bonus: crit threshold 29 of 255, the last ~113 ms of 1000.
    _at(emu, 6000)
    _press(emu)
    _at(emu, 6050)
    assert _gunblade(emu, 0, 4, luck=30) == ("hit", 1)
    assert emu.mem_read(t.HIT_MARKS, 1)[0] & 2
    _at(emu, 7000)
    _press(emu)
    _at(emu, 7500)
    assert _gunblade(emu, 0, 4, luck=30) == ("hit", 0)
    assert _sounds(emu) == [CRIT, OK]


def test_squalls_no_damage_call_is_not_judged():
    emu = _machine()
    _press(emu)
    _at(emu, 100)
    assert _gunblade(emu, 0, 4, landing=False) == ("hit", 0)
    assert _pressed(emu)[1] == 1, "his landing still has the press"


@pytest.mark.parametrize("lead,verdict,dealt", [(0, "crit", 2000), (187, "crit", 1502),
                                                (562, "hit", 500), (748, "hit", 2)])
def test_continuous_grading_on_an_attack(lead, verdict, dealt):
    """0 where the hit window opens, normal where the crit window opens, crit at impact.
    The game's damage reaching 00491124 is 1000, or 2000 for a crit."""
    emu = _machine(window=1000, continuous=True)
    assert _attack(emu, 10000 - lead, 10000) == verdict
    assert _damage(emu, 2000 if verdict == "crit" else 1000) == dealt
    assert _damage(emu, 1000) == 1000, "the next hit is not graded again"


@pytest.mark.parametrize("lead,verdict,taken", [(850, "hit", 505), (899, "hit", 1000),
                                                (950, "crit", 1504), (None, "crit", 2000)])
def test_continuous_grading_on_a_block(lead, verdict, taken):
    """0 at the dodge band's edge, normal at the normal band's far edge, crit at W."""
    emu = _machine(window=1000, continuous=True)
    assert _block(emu, None if lead is None else 10000 - lead, 10000) == verdict
    assert _damage(emu, 2000 if verdict == "crit" else 1000) == taken


def test_without_continuous_grading_damage_is_the_games():
    emu = _machine(window=1000)
    assert _attack(emu, 10000 - 562, 10000) == "hit"
    assert _damage(emu, 1000) == 1000


def test_square_records_the_time_and_other_buttons_do_not():
    emu = _machine(1000)
    _press(emu, 0x08 | 0x20)
    assert _pressed(emu) == (0, 0)
    _press(emu, 0x80 | 0x20)
    assert _pressed(emu) == (1000, 1)


def test_a_fumble_sounds_at_once_and_only_once():
    """Lexer, 2026-09-27: mashing with Irvine or Quistis failed at once; with
    Squall it was silent until the very end, then sounded two or three times."""
    emu = _machine(1000, window=150)
    _press(emu)
    assert _sounds(emu) == []
    _at(emu, 1030)
    _press(emu)
    assert _sounds(emu) == [FAIL], "the second press fails right away"
    for now in range(1060, 4000, 60):   # Squall's long run-up
        _at(emu, now)
        _press(emu)
    assert _sounds(emu) == [FAIL]
    _at(emu, 4010)
    assert _gunblade(emu, 0, 4) == ("miss", 0)
    assert _sounds(emu) == [FAIL], "the hit adds no second sound"


def test_a_late_press_gets_nothing_and_times_the_next_hit():
    """Lexer: the window is only before the hit; late inputs get nothing."""
    emu = _machine(window=1000)
    assert _attack(emu, None, 1000) == "miss"
    # Irvine's next shot lands 300 ms later: the late press times it.
    assert _attack(emu, 1100, 1300) == "crit"
    assert _attack(emu, 1350, 1600) == "crit"
    assert _sounds(emu) == [CRIT, CRIT]


def test_hext_and_hooks():
    assert t.build_hext(False) == ""
    text = t.build_hext(True, window_ms=1000, success_sound=12, crit_sound=13, failure_sound=34,
                        continuous=True)
    assert f"\n{t.DATA:X} = {t.data_bytes(1000, 12, 13, 34, True).hex(' ').upper()}" in text
    for site in (t.INPUT_HOOK, t.HIT_HOOK, t.AUTO_HOOK, t.GUNBLADE_HOOK):
        assert f"\n{site:X} = E9" in text
    for site in (t.HIT_ROLL_CALL, t.CRIT_ROLL_CALL, t.E10_AUTO_CRIT_CALL, t.E10_HIT_ROLL_CALL,
                 t.E10_CRIT_ROLL_CALL):
        assert f"\n{site:X} = E8" in text
    assert "4922B0 =" not in text, "the attack-type hook is gone"
    assert t.CAVE + len(t.CODE) <= t.DATA
    for bad in ({"window_ms": 10}, {"window_ms": 2001}, {"success_sound": 0}, {"crit_sound": 0},
                {"failure_sound": True}, {"continuous": 1}):
        with pytest.raises(ValueError):
            t.build_hext(True, **bad)


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
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
    assert loaded["timedHitsLimits"]["timedHitsWindow"]["maximum"] == 2000
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
        for bad in ({"timedHitsWindow": 5}, {"timedHitsCritSound": "9"}, {"timedHitsContinuous": 1}):
            with pytest.raises(ValueError):
                gameplay_settings.save({**data, **bad}, game, project, runtime_root=runtime)
