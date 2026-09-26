"""In-game SFX and Music sliders (#498): cave behaviour under unicorn.

The real cave bytes run with the kernel32 imports stubbed and the game's
music setter replaced by a probe. They must route the Music row to its own
byte and leave every other row's config byte and the CPU flags untouched,
scale music by the slider, load and save the global file, and supply the
SFX/Music labels.
"""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import kernel_text
from plugins.ff8 import music_volume_issue_498 as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
CREATE, READ, WRITE, CLOSE = 0x00F00000, 0x00F00010, 0x00F00020, 0x00F00030
STUBS = {m.IAT_CREATE_FILE_A: (CREATE, 0x1C), m.IAT_READ_FILE: (READ, 0x14),
         m.IAT_WRITE_FILE: (WRITE, 0x14), m.IAT_CLOSE_HANDLE: (CLOSE, 0x04)}
RETURN = 0x00D00000


class Game:
    def __init__(self, saved: int | None = None):
        self.emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        for base, size in ((0x00400000, 0x00800000), (0x00D00000, 0x00300000),
                           (0x01CFE000, 0x1000), (0x027AA000, 0x2000)):
            self.emu.mem_map(base, size)
        self.emu.mem_write(m.CAVE, m.CODE)
        self.emu.mem_write(m.DATA, m.data_bytes(m.TABLE_ORIGINAL))
        self.emu.mem_write(m.CONFIG_BLOCK, bytes(range(20)))
        for slot, (stub, pop) in STUBS.items():
            self.emu.mem_write(slot, struct.pack("<I", stub))
            self.emu.mem_write(stub, b"\xC2" + struct.pack("<H", pop))
        # The game's setter: jump into the cave as the Hext hook does; the
        # resume point records the (scaled) argument and returns.
        self.emu.mem_write(m.MUSIC_SETTER, m._jump(m.MUSIC_SETTER, m.ENTRY["music_setter"], 7))
        self.emu.mem_write(m.MUSIC_SETTER_RESUME, bytes.fromhex("89 0D 00 0F D0 00 83 C4 08 C3"))
        self.emu.mem_write(RETURN, b"\xF4")
        self.saved = saved
        self.written = []
        self.emu.hook_add(unicorn.UC_HOOK_CODE, self._imports)

    def _imports(self, uc, address, _size, _data):
        esp = uc.reg_read(x86.UC_X86_REG_ESP)
        args = struct.unpack("<5I", uc.mem_read(esp + 4, 20))
        if address == CREATE:
            reading = args[1] == 0x80000000
            ok = not reading or self.saved is not None
            uc.reg_write(x86.UC_X86_REG_EAX, 0x77 if ok else 0xFFFFFFFF)
        elif address == READ:
            uc.mem_write(args[1], bytes((self.saved,)))
            uc.mem_write(args[3], struct.pack("<I", 1))
            uc.reg_write(x86.UC_X86_REG_EAX, 1)
        elif address == WRITE:
            self.written.append(bytes(uc.mem_read(args[1], args[2])))
            uc.reg_write(x86.UC_X86_REG_EAX, 1)

    def byte(self, address):
        return self.emu.mem_read(address, 1)[0]

    def run(self, start, registers=None, stack=(), end=RETURN, eflags=0x202):
        esp = STACK + 0x1000
        self.emu.mem_write(esp, struct.pack(f"<{len(stack) + 1}I", RETURN, *stack))
        self.emu.reg_write(x86.UC_X86_REG_ESP, esp)
        self.emu.reg_write(x86.UC_X86_REG_EFLAGS, eflags)
        for register, value in (registers or {}).items():
            self.emu.reg_write(register, value)
        self.emu.emu_start(start, end + 1, count=20000)
        assert self.emu.reg_read(x86.UC_X86_REG_EIP) in (end, end + 1)


def _site(address):
    return next(site for site in m.CONFIG_SITES if site[0] == address)


REGISTER = {"eax": x86.UC_X86_REG_EAX, "ecx": x86.UC_X86_REG_ECX, "edx": x86.UC_X86_REG_EDX}
VALUE = {"al": (x86.UC_X86_REG_EAX, 0), "bl": (x86.UC_X86_REG_EBX, 0), "dl": (x86.UC_X86_REG_EDX, 0)}


@pytest.mark.parametrize("site", [site for site in m.CONFIG_SITES if not site[3]], ids=lambda s: f"{s[0]:08X}")
def test_reads_route_music_row_and_keep_flags(site):
    address, index, value, _store = site
    game = Game(saved=40)
    game.emu.mem_write(address + 6, b"\xF4")
    game.run(m.ENTRY[f"site_{address:x}"], {REGISTER[index]: m.MUSIC_MARK}, end=address + 6, eflags=0x246)
    register, _shift = VALUE[value]
    assert game.emu.reg_read(register) & 0xFF == 40, "the Music row reads the saved Music value"
    assert game.emu.reg_read(x86.UC_X86_REG_EFLAGS) & 0x8D5 == 0x246 & 0x8D5, "flags survive"
    game = Game()
    game.emu.mem_write(address + 6, b"\xF4")
    game.run(m.ENTRY[f"site_{address:x}"], {REGISTER[index]: 3}, end=address + 6, eflags=0x202)
    assert game.emu.reg_read(register) & 0xFF == 3, "other rows read their own config byte"
    assert game.emu.reg_read(x86.UC_X86_REG_EFLAGS) & 0x8D5 == 0x202 & 0x8D5


def test_music_store_applies_scaled_volume_and_saves_the_file():
    address, index, value, _store = _site(0x004EE2F6)
    game = Game()
    game.emu.mem_write(address + 6, b"\xF4")
    game.emu.mem_write(m.LAST_REQUEST, struct.pack("<I", 100))
    game.emu.mem_write(m.LOADED, b"\x01")
    game.run(m.ENTRY[f"site_{address:x}"], {REGISTER[index]: m.MUSIC_MARK, x86.UC_X86_REG_EBX: 25},
             end=address + 6)
    assert game.byte(m.MUSIC) == 25
    assert game.written == [b"\x19"], "the new value is saved to the global file"
    assert struct.unpack("<I", game.emu.mem_read(0x00D00F00, 4))[0] == 25, "100 x 25% = 25"
    assert game.byte(m.CONFIG_BLOCK + 3) == 3, "SFX's per-save byte is untouched"


def test_other_row_store_writes_its_config_byte():
    address, index, value, _store = _site(0x004EE2F6)
    game = Game()
    game.emu.mem_write(address + 6, b"\xF4")
    game.run(m.ENTRY[f"site_{address:x}"], {REGISTER[index]: 3, x86.UC_X86_REG_EBX: 77}, end=address + 6)
    assert game.byte(m.CONFIG_BLOCK + 3) == 77
    assert game.written == []


@pytest.mark.parametrize("saved,requested,expected", [(None, 127, 127), (50, 127, 63), (0, 90, 0), (101, 127, 127)])
def test_music_setter_scales_by_the_saved_slider(saved, requested, expected):
    game = Game(saved=saved)
    game.run(m.MUSIC_SETTER, stack=(requested, 0))
    assert struct.unpack("<I", game.emu.mem_read(0x00D00F00, 4))[0] == expected
    assert struct.unpack("<I", game.emu.mem_read(m.LAST_REQUEST, 4))[0] == requested


@pytest.mark.parametrize("text_id,part,label", [
    (m.SOUND_TEXT, 0, "SFX"), (m.SOUND_TEXT, 1, "Sound effect volume"),
    (m.MUSIC_ID, 0, "Music"), (m.MUSIC_ID, 1, "Music volume")])
def test_labels(text_id, part, label):
    game = Game()
    game.run(m.ENTRY["text_lookup"], stack=(1, 2, text_id, part))
    pointer = game.emu.reg_read(x86.UC_X86_REG_EAX)
    encoded = kernel_text.encode(label, compress=False)
    assert bytes(game.emu.mem_read(pointer, len(encoded) + 1)) == encoded + b"\0"


def test_other_text_goes_to_the_game():
    game = Game()
    game.emu.mem_write(m.TEXT_LOOKUP_RESUME, b"\xF4")
    game.run(m.ENTRY["text_lookup"], stack=(1, 2, 0x36, 0), end=m.TEXT_LOOKUP_RESUME)
    assert game.emu.reg_read(x86.UC_X86_REG_EAX) == 1


def test_table_adds_music_after_sound_and_keeps_the_rest():
    data = m.data_bytes(m.TABLE_ORIGINAL)
    table = data[m.NEW_TABLE - m.DATA:]
    rows = [table[i:i + 16] for i in range(0, len(table), 16)]
    assert len(rows) == 11
    assert rows[:9] == [m.TABLE_ORIGINAL[i:i + 16] for i in range(0, 144, 16)]
    assert struct.unpack("<HHHHH", rows[9][:10]) == (m.MUSIC_ID, 0, 0, m.VOLUME_SLIDER, m.MUSIC_MARK)
    assert struct.unpack("<H", rows[10][:2])[0] == 0xFFFF


def test_off_writes_nothing_and_on_touches_every_site():
    assert m.build_hext(False) == ""
    text = m.build_hext(True)
    for site, _original in m.verified_hooks():
        if site != m.TABLE:
            assert f"\n{site:X} = " in text
    with pytest.raises(ValueError):
        m.build_hext("yes")


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    code, entry = m._assemble()
    assert code == m.CODE
    assert entry == m.ENTRY
