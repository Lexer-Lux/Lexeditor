"""Timed Hits and Blocks (#482/#483): the press recorder and the hit scaler under unicorn."""
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


def _machine(now: int, *, window=250, bonus=150, block=50, ok=7, fail=9, physical_only=False):
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00800000), (0x00E00000, 0x00010000),
                       (0x01D27000, 0x2000), (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(t.CAVE, t.CODE)
    emu.mem_write(t.DATA, t.data_bytes(window, bonus, block, ok, fail, physical_only))
    emu.mem_write(t.TIME_GET_TIME, struct.pack("<I", TIME_STUB))
    emu.mem_write(TIME_STUB, b"\xA1" + struct.pack("<I", CLOCK) + b"\xC3")  # mov eax,[CLOCK]; ret
    emu.mem_write(CLOCK, struct.pack("<I", now))
    # Sound stand-in: append [esp+4] to the SOUNDS list (count first).
    stub = bytes.fromhex("8B 44 24 04 8B 0D") + struct.pack("<I", SOUNDS)
    stub += bytes.fromhex("89 04 8D") + struct.pack("<I", SOUNDS + 4)
    stub += bytes.fromhex("FF 05") + struct.pack("<I", SOUNDS) + b"\xC3"
    emu.mem_write(t.PLAY_SOUND, stub)
    for resume in (t.INPUT_RESUME, t.HIT_RESUME, t.TYPE_RESUME):
        emu.mem_write(resume, b"\xF4")
    return emu


def _sounds(emu):
    count = struct.unpack("<I", emu.mem_read(SOUNDS, 4))[0]
    return list(struct.unpack(f"<{count}I", emu.mem_read(SOUNDS + 4, 4 * count))) if count else []


def _press(emu, pressed_bits: int):
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


def _hit(emu, attacker: int, target: int, damage: int) -> int:
    emu.mem_write(t.ATTACKER, bytes((attacker,)))
    esp = STACK + 0x8000
    frame = bytearray(0x20)
    struct.pack_into("<I", frame, 0x10, target * 0xD0)
    emu.mem_write(esp, bytes(frame))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, damage)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.emu_start(t.HIT_ENTRY, t.HIT_RESUME + 1, count=500)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0xD1D1D1D1
    return emu.reg_read(x86.UC_X86_REG_ESI)


def _pressed(emu):
    return struct.unpack("<II", emu.mem_read(t.PRESS_TIME, 8))


def test_square_records_the_time_and_other_buttons_do_not():
    emu = _machine(1000)
    # R1 is Look Right (Universal Item) and the Modern Controls fire bit.
    _press(emu, 0x08 | 0x20)
    assert _pressed(emu) == (0, 0)
    _press(emu, 0x80 | 0x20)
    assert _pressed(emu) == (1000, 1)


def test_a_timed_party_hit_gets_the_bonus_once():
    emu = _machine(1000, ok=7)
    _press(emu, 0x80)
    emu.mem_write(CLOCK, struct.pack("<I", 1200))
    assert _hit(emu, 1, 4, 1000) == 1500
    assert _sounds(emu) == [7]
    assert _pressed(emu)[1] == 0, "the press is used up"
    assert _hit(emu, 1, 4, 1000) == 1000, "a second hit needs its own press"


def test_a_timed_block_reduces_an_enemy_hit_on_the_party():
    emu = _machine(1000, block=50)
    _press(emu, 0x80)
    emu.mem_write(CLOCK, struct.pack("<I", 1100))
    assert _hit(emu, 5, 0, 801) == 400


def test_an_early_press_misses_with_the_failure_sound():
    emu = _machine(1000, fail=9)
    _press(emu, 0x80)
    emu.mem_write(CLOCK, struct.pack("<I", 1400))  # 400 ms: outside 250, inside 750
    assert _hit(emu, 0, 3, 1000) == 1000
    assert _sounds(emu) == [9]


def test_a_press_long_before_is_ignored_silently():
    emu = _machine(1000)
    _press(emu, 0x80)
    emu.mem_write(CLOCK, struct.pack("<I", 5000))
    assert _hit(emu, 0, 3, 1000) == 1000
    assert _sounds(emu) == []


def test_party_on_party_and_healing_are_left_alone():
    emu = _machine(1000)
    _press(emu, 0x80)
    assert _hit(emu, 0, 1, 1000) == 1000
    assert _hit(emu, 0, 3, 0) == 0
    assert _pressed(emu)[1] == 1, "the press waits for a hit it applies to"


def test_hext_and_hooks():
    assert t.build_hext(False) == ""
    text = t.build_hext(True, window_ms=300, bonus_percent=200, block_percent=25,
                        success_sound=12, failure_sound=34)
    assert f"\n{t.DATA:X} = {t.data_bytes(300, 200, 25, 12, 34).hex(' ').upper()}" in text
    assert f"\n{t.HIT_HOOK:X} = E9" in text and f"\n{t.INPUT_HOOK:X} = E9" in text
    for bad in ({"window_ms": 10}, {"bonus_percent": 99}, {"block_percent": 101},
                {"success_sound": 0}, {"failure_sound": True}):
        with pytest.raises(ValueError):
            t.build_hext(True, **bad)


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    assert t._assemble() == (t.CODE, t.HIT_ENTRY, t.TYPE_ENTRY)


def _damage_type(emu, kind: int):
    """Enter 004922B0(kind, ...) through the recorder, as 0048FE20 does."""
    esp = STACK + 0x7000
    emu.mem_write(esp, struct.pack("<II", 0xCAFEF00D, kind))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.emu_start(t.TYPE_ENTRY, t.TYPE_RESUME + 1, count=50)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp


@pytest.mark.parametrize("kind,counts", [(1, True), (7, True), (9, True), (10, True), (36, True),
                                         (2, False), (8, False), (11, False), (22, False)])
def test_physical_only_times_physical_hits_and_keeps_the_press_otherwise(kind, counts):
    emu = _machine(1000, ok=7, physical_only=True)
    _press(emu, t.SQUARE)
    emu.mem_write(CLOCK, struct.pack("<I", 1200))
    _damage_type(emu, kind)
    assert _hit(emu, 1, 4, 1000) == (1500 if counts else 1000)
    # A spell that is ignored leaves the press for the next physical hit.
    assert _pressed(emu)[1] == (0 if counts else 1)


def test_every_damaging_hit_counts_by_default():
    emu = _machine(1000, ok=7)
    _press(emu, t.SQUARE)
    emu.mem_write(CLOCK, struct.pack("<I", 1200))
    _damage_type(emu, 2)  # Magic Attack
    assert _hit(emu, 1, 4, 1000) == 1500


def test_settings_round_trip_and_reach_the_patch(tmp_path):
    from unittest.mock import patch
    project, game, runtime = tmp_path / "mod", tmp_path / "game", tmp_path / "runtime"
    project.mkdir()
    game.mkdir()
    gameplay_settings.initialize_project(project)
    loaded = gameplay_settings.load(project, game)
    assert loaded["timedHits"] is False and loaded["timedHitsWindow"] == t.DEFAULT_WINDOW_MS
    assert loaded["timedHitsLimits"]["timedBlocksDamage"]["maximum"] == 100
    with patch.object(gameplay_settings, "_verify_executable", return_value=game / "FF8_EN.exe"):
        data = {**loaded, "timedHits": True, "timedHitsWindow": 300, "timedHitsBonus": 200,
                "timedBlocksDamage": 25, "timedHitsSuccessSound": 40, "timedHitsFailureSound": 41}
        gameplay_settings.save(data, game, project, runtime_root=runtime)
        saved = gameplay_settings.load(project, game)
        for key in ("timedHits", "timedHitsWindow", "timedHitsBonus", "timedBlocksDamage",
                    "timedHitsSuccessSound", "timedHitsFailureSound"):
            assert saved[key] == data[key], key
        patch_text = gameplay_settings.patch_path(project).read_text(encoding="utf-8")
        assert f"{t.DATA:X} = {t.data_bytes(300, 200, 25, 40, 41).hex(' ').upper()}" in patch_text
        for bad in ({"timedHitsWindow": 5}, {"timedHitsBonus": "150"}, {"timedHits": 1}):
            with pytest.raises(ValueError):
                gameplay_settings.save({**data, **bad}, game, project, runtime_root=runtime)


def _at(emu, now: int):
    emu.mem_write(CLOCK, struct.pack("<I", now))


def test_mashing_fumbles_instead_of_winning():
    """Lexer mashed Square and won every hit and every block."""
    emu = _machine(1000, ok=7, fail=9)
    for now in range(1000, 1300, 50):
        _at(emu, now)
        _press(emu, t.SQUARE)
    _at(emu, 1320)
    assert _hit(emu, 1, 4, 1000) == 1000
    assert _hit(emu, 5, 0, 1000) == 1000  # the enemy's hit on the party too
    assert _sounds(emu) == [9]


def test_a_block_far_too_early_misses():
    emu = _machine(1000, window=150, ok=7, fail=9)
    _press(emu, t.SQUARE)
    _at(emu, 1400)                       # 400 ms early, inside three windows
    assert _hit(emu, 5, 0, 1000) == 1000
    assert _sounds(emu) == [9]


def test_a_press_just_after_the_hit_is_too_late_once():
    emu = _machine(1000, window=150, ok=7, fail=9)
    assert _hit(emu, 1, 4, 1000) == 1000  # no press yet
    for now in (1050, 1080, 1120):
        _at(emu, now)
        _press(emu, t.SQUARE)
    assert _sounds(emu) == [9]            # one too-late sound, however many presses
    _at(emu, 1130)
    assert _hit(emu, 1, 4, 1000) == 1000  # and nothing was armed by them


def test_squalls_second_call_for_the_same_swing_is_not_judged_again():
    emu = _machine(1000, window=150, ok=7, fail=9)
    _press(emu, t.SQUARE)
    _at(emu, 1100)
    assert _hit(emu, 0, 4, 1000) == 1500  # the normal path
    _at(emu, 1110)
    _press(emu, t.SQUARE)                 # a press between the two calls
    _at(emu, 1120)
    assert _hit(emu, 0, 4, 1000) == 1000  # 00485160's call: no second bonus
    assert _sounds(emu) == [7, 9]


def test_an_old_early_press_is_forgotten_not_held_against_the_player():
    emu = _machine(1000, window=150, ok=7, fail=9)
    _press(emu, t.SQUARE)
    _at(emu, 2000)                        # far older than three windows
    _press(emu, t.SQUARE)                 # a fresh press, not a fumble
    _at(emu, 2100)
    assert _hit(emu, 1, 4, 1000) == 1500
    assert _sounds(emu) == [7]
