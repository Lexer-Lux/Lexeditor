"""In-game SFX and Music sliders (issue #498).

Adds a Music row under the Config menu's Sound slider and renames Sound to
SFX. SFX keeps the vanilla behaviour and stays in each save. Music is one
global value, stored in `lexeditor-music-volume.dat` beside the game (Lexer,
2026-09-26: the save's 20-byte config block has no free byte).

How it works, all against FF8_EN.exe SHA-256 064d466b...9570:

- The Config menu is table-driven: 16-byte rows at 00B88970, ended by an
  FFFF row that other data follows. The table is copied to a cave with a
  Music row inserted after Sound, and every instruction that reads it is
  repointed. The row count is computed from the terminator at runtime.
- Music uses the generic 0-100 slider type 0x21 with config offset
  MUSIC_MARK. The menu touches config bytes in nine 6-byte `mov`s of the
  form `[reg + 01CFE738]`. Each is redirected through a stub that uses the
  Music byte when the offset is MUSIC_MARK and runs the original otherwise.
  The flags are preserved, because `cmp` results are live across some of them.
- Writing the Music value re-applies the music volume and saves the file.
- Music gain is applied at the game's music-volume setter 0046C6F0 (target
  0-127). Its argument is scaled by Music/100, and the last unscaled request
  is kept so a slider change can re-apply it. This is the DirectMusic path;
  with FFNx external music enabled, FFNx sets its own volume and bypasses it.
- Labels come from menu text bank 2 through 004BD630 (id, 0 = label; id, 1
  = help). A wrapper returns FF8-encoded "SFX"/"Music" and their help lines
  for Sound's id 0x35 and for MUSIC_ID.

Off by default: with it off, no byte is written.
"""

from __future__ import annotations

import struct

from . import kernel_text

DEFAULT_SPLIT_MUSIC_VOLUME = False

CONFIG_BLOCK = 0x01CFE738
TABLE = 0x00B88970
TABLE_ROWS = 9  # before the FFFF terminator
ROW_SIZE = 16
SOUND_TEXT = 0x35
MUSIC_ID = 0x7E
MUSIC_MARK = 0xFFFE
VOLUME_SLIDER = 0x21

TEXT_LOOKUP = 0x004BD630
TEXT_LOOKUP_ORIGINAL = bytes.fromhex("8B 44 24 04 85 C0")
TEXT_LOOKUP_RESUME = 0x004BD636
MUSIC_SETTER = 0x0046C6F0
MUSIC_SETTER_ORIGINAL = bytes.fromhex("8B 4C 24 04 83 EC 08")
MUSIC_SETTER_RESUME = 0x0046C6F7

IAT_CREATE_FILE_A = 0x00B691C8
IAT_READ_FILE = 0x00B691C0
IAT_WRITE_FILE = 0x00B690AC
IAT_CLOSE_HANDLE = 0x00B69078

# Every Config-menu access to a config byte: (site, register holding the
# offset, value register, is_store). Each is `mov r8, [idx + 01CFE738]` or
# the store form, 6 bytes long.
CONFIG_SITES = (
    (0x004EDD96, "eax", "dl", False),
    (0x004EDDD4, "edx", "al", False),
    (0x004EE27C, "ecx", "bl", False),
    (0x004EE299, "ecx", "al", True),
    (0x004EE2F6, "edx", "bl", True),
    (0x004EE31A, "ecx", "bl", False),
    (0x004EE359, "eax", "bl", True),
    (0x004EECA1, "edx", "al", False),
    (0x004EED11, "eax", "dl", False),
)
_MODRM = {("eax", "dl"): 0x90, ("edx", "al"): 0x82, ("ecx", "bl"): 0x99,
          ("ecx", "al"): 0x81, ("edx", "bl"): 0x9A, ("eax", "bl"): 0x98}


def site_original(index: str, value: str, store: bool) -> bytes:
    return bytes((0x88 if store else 0x8A, _MODRM[(index, value)])) + struct.pack("<I", CONFIG_BLOCK)


# Instructions that address the row table by displacement.
TABLE_SITES = (
    0x004EDD66, 0x004EDD75, 0x004EDD8F, 0x004EDDC0, 0x004EDDCD, 0x004EDDEF,
    0x004EE0DA, 0x004EE0F9, 0x004EE160, 0x004EE1A8, 0x004EE1CD, 0x004EE1D4,
    0x004EE20E, 0x004EE215, 0x004EE26C, 0x004EE275, 0x004EE292, 0x004EE2E8,
    0x004EE2EF, 0x004EE30D, 0x004EE352, 0x004EEB88,
)

CAVE = 0x027AA000
DATA = 0x027AAC00
MUSIC = DATA + 0x00          # byte, 0-100
LOADED = DATA + 0x01         # byte
LAST_REQUEST = DATA + 0x04   # dword, last unscaled 0-127 target
SCRATCH = DATA + 0x08        # dword, bytes read/written
FILE_NAME = DATA + 0x10
SFX_LABEL = DATA + 0x30
SFX_HELP = DATA + 0x40
MUSIC_LABEL = DATA + 0x60
MUSIC_HELP = DATA + 0x70
NEW_TABLE = DATA + 0x100
FILE_NAME_TEXT = "lexeditor-music-volume.dat"
LABELS = {
    SFX_LABEL: "SFX", SFX_HELP: "Sound effect volume",
    MUSIC_LABEL: "Music", MUSIC_HELP: "Music volume",
}


def _stubs() -> str:
    lines = []
    for site, index, value, store in CONFIG_SITES:
        name = f"site_{site:x}"
        access = f"byte ptr [{index} + {CONFIG_BLOCK:#x}]"
        lines += [
            f"{name}:",
            "    pushfd",
            f"    cmp {index}, {MUSIC_MARK:#x}",
            f"    jne {name}_vanilla",
            "    popfd",
        ]
        if store:
            lines += [
                f"    mov byte ptr [{MUSIC:#x}], {value}",
                "    pushfd",
                "    call music_changed",
                "    popfd",
            ]
        else:
            lines += [
                "    pushfd",
                "    call ensure_loaded",
                "    popfd",
                f"    mov {value}, byte ptr [{MUSIC:#x}]",
            ]
        lines += [
            f"    push {site + 6:#x}",
            "    ret",
            f"{name}_vanilla:",
            "    popfd",
            f"    mov {access}, {value}" if store else f"    mov {value}, {access}",
            f"    push {site + 6:#x}",
            "    ret",
        ]
    return "\n".join(lines)


ASSEMBLY = f"""
text_lookup:
    cmp dword ptr [esp + 8], 2
    jne text_vanilla
    mov eax, dword ptr [esp + 12]
    cmp eax, {SOUND_TEXT:#x}
    je text_sfx
    cmp eax, {MUSIC_ID:#x}
    je text_music
text_vanilla:
    mov eax, dword ptr [esp + 4]
    test eax, eax
    push {TEXT_LOOKUP_RESUME:#x}
    ret
text_sfx:
    mov eax, {SFX_LABEL:#x}
    cmp dword ptr [esp + 16], 0
    je text_done
    mov eax, {SFX_HELP:#x}
    cmp dword ptr [esp + 16], 1
    je text_done
    jmp text_vanilla
text_music:
    mov eax, {MUSIC_LABEL:#x}
    cmp dword ptr [esp + 16], 0
    je text_done
    mov eax, {MUSIC_HELP:#x}
text_done:
    ret

music_setter:
    call ensure_loaded
    mov ecx, dword ptr [esp + 4]
    cmp ecx, 0x7f
    ja music_setter_vanilla
    mov dword ptr [{LAST_REQUEST:#x}], ecx
    movzx eax, byte ptr [{MUSIC:#x}]
    imul eax, ecx
    xor edx, edx
    mov ecx, 100
    div ecx
    mov dword ptr [esp + 4], eax
music_setter_vanilla:
    mov ecx, dword ptr [esp + 4]
    sub esp, 8
    push {MUSIC_SETTER_RESUME:#x}
    ret

ensure_loaded:
    cmp byte ptr [{LOADED:#x}], 0
    jne ensure_done
    pushad
    mov byte ptr [{LOADED:#x}], 1
    mov byte ptr [{MUSIC:#x}], 100
    mov dword ptr [{LAST_REQUEST:#x}], 0x7f
    push 0
    push 0x80
    push 3
    push 0
    push 1
    push 0x80000000
    push {FILE_NAME:#x}
    call dword ptr [{IAT_CREATE_FILE_A:#x}]
    cmp eax, -1
    je ensure_popped
    mov esi, eax
    push 0
    push {SCRATCH:#x}
    push 1
    push {SCRATCH + 4:#x}
    push esi
    call dword ptr [{IAT_READ_FILE:#x}]
    cmp dword ptr [{SCRATCH:#x}], 1
    jne ensure_close
    movzx eax, byte ptr [{SCRATCH + 4:#x}]
    cmp eax, 100
    ja ensure_close
    mov byte ptr [{MUSIC:#x}], al
ensure_close:
    push esi
    call dword ptr [{IAT_CLOSE_HANDLE:#x}]
ensure_popped:
    popad
ensure_done:
    ret

music_changed:
    pushad
    push 0
    push dword ptr [{LAST_REQUEST:#x}]
    call {MUSIC_SETTER:#x}
    add esp, 8
    push 0
    push 0x80
    push 2
    push 0
    push 0
    push 0x40000000
    push {FILE_NAME:#x}
    call dword ptr [{IAT_CREATE_FILE_A:#x}]
    cmp eax, -1
    je changed_done
    mov esi, eax
    push 0
    push {SCRATCH:#x}
    push 1
    push {MUSIC:#x}
    push esi
    call dword ptr [{IAT_WRITE_FILE:#x}]
    push esi
    call dword ptr [{IAT_CLOSE_HANDLE:#x}]
changed_done:
    popad
    ret

{_stubs()}
"""


def _assemble() -> tuple[bytes, dict[str, int]]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code, _count = ks.asm(ASSEMBLY, CAVE)
    labels = {}
    for name in ("text_lookup", "music_setter", *(f"site_{site:x}" for site, *_ in CONFIG_SITES)):
        probe = ASSEMBLY.split(f"\n{name}:")[0] + f"\n{name}:\n nop"
        labels[name] = CAVE + len(ks.asm(probe, CAVE)[0]) - 1
    return bytes(code), labels


# Assembled at CAVE from ASSEMBLY (keystone); tests/ff8/test_ff8_music_volume_issue_498.py
# re-assembles and checks these, and runs the stubs under unicorn.
CODE = bytes.fromhex(
    "83 7C 24 08 02 75 0E 8B 44 24 0C 83 F8 35 74 11"
    "83 F8 7E 74 26 8B 44 24 04 85 C0 68 36 D6 4B 00"
    "C3 B8 30 AC 7A 02 83 7C 24 10 00 74 1F B8 40 AC"
    "7A 02 83 7C 24 10 01 74 13 EB DA B8 60 AC 7A 02"
    "83 7C 24 10 00 74 05 B8 70 AC 7A 02 C3 E8 33 00"
    "00 00 8B 4C 24 04 83 F9 7F 77 1D 89 0D 04 AC 7A"
    "02 0F B6 05 00 AC 7A 02 0F AF C1 31 D2 B9 64 00"
    "00 00 F7 F1 89 44 24 04 8B 4C 24 04 83 EC 08 68"
    "F7 C6 46 00 C3 80 3D 01 AC 7A 02 00 75 74 60 C6"
    "05 01 AC 7A 02 01 C6 05 00 AC 7A 02 64 C7 05 04"
    "AC 7A 02 7F 00 00 00 6A 00 68 80 00 00 00 6A 03"
    "6A 00 6A 01 68 00 00 00 80 68 10 AC 7A 02 FF 15"
    "C8 91 B6 00 83 F8 FF 74 38 89 C6 6A 00 68 08 AC"
    "7A 02 6A 01 68 0C AC 7A 02 56 FF 15 C0 91 B6 00"
    "83 3D 08 AC 7A 02 01 75 11 0F B6 05 0C AC 7A 02"
    "83 F8 64 77 05 A2 00 AC 7A 02 56 FF 15 78 90 B6"
    "00 61 C3 60 6A 00 FF 35 04 AC 7A 02 E8 DF 25 CC"
    "FD 83 C4 08 6A 00 68 80 00 00 00 6A 02 6A 00 6A"
    "00 68 00 00 00 40 68 10 AC 7A 02 FF 15 C8 91 B6"
    "00 83 F8 FF 74 1E 89 C6 6A 00 68 08 AC 7A 02 6A"
    "01 68 00 AC 7A 02 56 FF 15 AC 90 B6 00 56 FF 15"
    "78 90 B6 00 61 C3 9C 3D FE FF 00 00 75 14 9D 9C"
    "E8 20 FF FF FF 9D 8A 15 00 AC 7A 02 68 9C DD 4E"
    "00 C3 9D 8A 90 38 E7 CF 01 68 9C DD 4E 00 C3 9C"
    "81 FA FE FF 00 00 75 13 9D 9C E8 F6 FE FF FF 9D"
    "A0 00 AC 7A 02 68 DA DD 4E 00 C3 9D 8A 82 38 E7"
    "CF 01 68 DA DD 4E 00 C3 9C 81 F9 FE FF 00 00 75"
    "14 9D 9C E8 CD FE FF FF 9D 8A 1D 00 AC 7A 02 68"
    "82 E2 4E 00 C3 9D 8A 99 38 E7 CF 01 68 82 E2 4E"
    "00 C3 9C 81 F9 FE FF 00 00 75 13 9D A2 00 AC 7A"
    "02 9C E8 1C FF FF FF 9D 68 9F E2 4E 00 C3 9D 88"
    "81 38 E7 CF 01 68 9F E2 4E 00 C3 9C 81 FA FE FF"
    "00 00 75 14 9D 88 1D 00 AC 7A 02 9C E8 F2 FE FF"
    "FF 9D 68 FC E2 4E 00 C3 9D 88 9A 38 E7 CF 01 68"
    "FC E2 4E 00 C3 9C 81 F9 FE FF 00 00 75 14 9D 9C"
    "E8 50 FE FF FF 9D 8A 1D 00 AC 7A 02 68 20 E3 4E"
    "00 C3 9D 8A 99 38 E7 CF 01 68 20 E3 4E 00 C3 9C"
    "3D FE FF 00 00 75 14 9D 88 1D 00 AC 7A 02 9C E8"
    "9F FE FF FF 9D 68 5F E3 4E 00 C3 9D 88 98 38 E7"
    "CF 01 68 5F E3 4E 00 C3 9C 81 FA FE FF 00 00 75"
    "13 9D 9C E8 FD FD FF FF 9D A0 00 AC 7A 02 68 A7"
    "EC 4E 00 C3 9D 8A 82 38 E7 CF 01 68 A7 EC 4E 00"
    "C3 9C 3D FE FF 00 00 75 14 9D 9C E8 D5 FD FF FF"
    "9D 8A 15 00 AC 7A 02 68 17 ED 4E 00 C3 9D 8A 90"
    "38 E7 CF 01 68 17 ED 4E 00 C3"
)
ENTRY = {
    "text_lookup": 0x027aa000,
    "music_setter": 0x027aa04d,
    "site_4edd96": 0x027aa156,
    "site_4eddd4": 0x027aa17f,
    "site_4ee27c": 0x027aa1a8,
    "site_4ee299": 0x027aa1d2,
    "site_4ee2f6": 0x027aa1fb,
    "site_4ee31a": 0x027aa225,
    "site_4ee359": 0x027aa24f,
    "site_4eeca1": 0x027aa278,
    "site_4eed11": 0x027aa2a1,
}
TABLE_ORIGINAL = bytes.fromhex(
    "38 00 39 00 3A 00 01 00 20 00 00 00 20 DD 4E 00"
    "11 00 13 00 12 00 00 00 04 00 00 00 00 00 00 00"
    "0E 00 0F 00 10 00 00 00 01 00 00 00 00 00 00 00"
    "3D 00 3F 00 3E 00 00 00 00 01 00 00 00 00 00 00"
    "0B 00 00 00 00 00 05 00 06 00 00 00 00 00 00 00"
    "06 00 00 00 00 00 03 00 00 00 00 00 00 00 00 00"
    "07 00 00 00 00 00 03 00 01 00 00 00 00 00 00 00"
    "08 00 00 00 00 00 03 00 02 00 00 00 00 00 00 00"
    "35 00 00 00 00 00 21 00 03 00 00 00 00 00 00 00"
    "FF FF 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
)
TABLE_SITE_BYTES = {
    0x004edd66: (bytes.fromhex("66 39 99 70 89 B8 00"), bytes.fromhex("66 39 99 00 AD 7A 02")),
    0x004edd75: (bytes.fromhex("66 8B 81 76 89 B8 00"), bytes.fromhex("66 8B 81 06 AD 7A 02")),
    0x004edd8f: (bytes.fromhex("66 8B 81 78 89 B8 00"), bytes.fromhex("66 8B 81 08 AD 7A 02")),
    0x004eddc0: (bytes.fromhex("66 89 91 7A 89 B8 00"), bytes.fromhex("66 89 91 0A AD 7A 02")),
    0x004eddcd: (bytes.fromhex("66 8B 91 78 89 B8 00"), bytes.fromhex("66 8B 91 08 AD 7A 02")),
    0x004eddef: (bytes.fromhex("66 89 81 7A 89 B8 00"), bytes.fromhex("66 89 81 0A AD 7A 02")),
    0x004ee0da: (bytes.fromhex("66 8B 81 70 89 B8 00"), bytes.fromhex("66 8B 81 00 AD 7A 02")),
    0x004ee0f9: (bytes.fromhex("66 8B 88 76 89 B8 00"), bytes.fromhex("66 8B 88 06 AD 7A 02")),
    0x004ee160: (bytes.fromhex("66 8B 88 78 89 B8 00"), bytes.fromhex("66 8B 88 08 AD 7A 02")),
    0x004ee1a8: (bytes.fromhex("66 8B BA 78 89 B8 00"), bytes.fromhex("66 8B BA 08 AD 7A 02")),
    0x004ee1cd: (bytes.fromhex("66 8B 88 78 89 B8 00"), bytes.fromhex("66 8B 88 08 AD 7A 02")),
    0x004ee1d4: (bytes.fromhex("8B 80 7C 89 B8 00"), bytes.fromhex("8B 80 0C AD 7A 02")),
    0x004ee20e: (bytes.fromhex("66 8B 90 78 89 B8 00"), bytes.fromhex("66 8B 90 08 AD 7A 02")),
    0x004ee215: (bytes.fromhex("8B 80 7C 89 B8 00"), bytes.fromhex("8B 80 0C AD 7A 02")),
    0x004ee26c: (bytes.fromhex("66 8B 88 78 89 B8 00"), bytes.fromhex("66 8B 88 08 AD 7A 02")),
    0x004ee275: (bytes.fromhex("66 39 B8 70 89 B8 00"), bytes.fromhex("66 39 B8 00 AD 7A 02")),
    0x004ee292: (bytes.fromhex("66 8B 8A 78 89 B8 00"), bytes.fromhex("66 8B 8A 08 AD 7A 02")),
    0x004ee2e8: (bytes.fromhex("66 8B 90 78 89 B8 00"), bytes.fromhex("66 8B 90 08 AD 7A 02")),
    0x004ee2ef: (bytes.fromhex("66 39 B8 70 89 B8 00"), bytes.fromhex("66 39 B8 00 AD 7A 02")),
    0x004ee30d: (bytes.fromhex("66 8B 88 78 89 B8 00"), bytes.fromhex("66 8B 88 08 AD 7A 02")),
    0x004ee352: (bytes.fromhex("66 8B 82 78 89 B8 00"), bytes.fromhex("66 8B 82 08 AD 7A 02")),
    0x004eeb88: (bytes.fromhex("BD 76 89 B8 00"), bytes.fromhex("BD 06 AD 7A 02")),
}


def data_bytes(original_table: bytes) -> bytes:
    """The data block, including the relocated table built from the exe's own rows."""
    if len(original_table) != (TABLE_ROWS + 1) * ROW_SIZE:
        raise ValueError("Config table must be the 9 native rows plus the FFFF terminator")
    rows = [original_table[i * ROW_SIZE:(i + 1) * ROW_SIZE] for i in range(TABLE_ROWS + 1)]
    if struct.unpack_from("<H", rows[8])[0] != SOUND_TEXT or struct.unpack_from("<H", rows[9])[0] != 0xFFFF:
        raise ValueError("Config table does not match the verified build")
    music_row = struct.pack("<HHHHHHI", MUSIC_ID, 0, 0, VOLUME_SLIDER, MUSIC_MARK, 0, 0)
    table = b"".join(rows[:9]) + music_row + rows[9]
    block = bytearray(0x100)
    block[FILE_NAME - DATA:FILE_NAME - DATA + len(FILE_NAME_TEXT) + 1] = FILE_NAME_TEXT.encode("ascii") + b"\0"
    for address, text in LABELS.items():
        encoded = kernel_text.encode(text, compress=False) + b"\0"
        block[address - DATA:address - DATA + len(encoded)] = encoded
    return bytes(block) + table


def _jump(site: int, target: int, length: int) -> bytes:
    return b"\xE9" + (target - (site + 5)).to_bytes(4, "little", signed=True) + b"\x90" * (length - 5)


def table_site_patch(site: int, original: bytes) -> bytes:
    """Repoint one table reference: replace its displacement, keep the offset into a row."""
    for field in range(0, ROW_SIZE):
        needle = struct.pack("<I", TABLE + field)
        at = original.find(needle)
        if at != -1:
            return original[:at] + struct.pack("<I", NEW_TABLE + field) + original[at + 4:]
    raise ValueError(f"No Config table displacement in the instruction at {site:08X}")


def build_hext(enabled: bool) -> str:
    """The tweak's Hext fragment, or nothing when it is off.

    Every byte is embedded and was derived from the verified executable;
    gameplay_settings checks each hook site's original bytes against the
    installed game before this is written.
    """
    if not isinstance(enabled, bool):
        raise ValueError("SFX and Music sliders must be true or false")
    if not enabled:
        return ""
    data = data_bytes(TABLE_ORIGINAL)
    lines = [
        "# SFX and Music sliders (#498): Music row, labels, music gain, lexeditor-music-volume.dat.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{DATA:X}:{len(data):X}",
        f"{DATA:X} = {data.hex(' ').upper()}",
        f"{TEXT_LOOKUP:X} = {_jump(TEXT_LOOKUP, ENTRY['text_lookup'], 6).hex(' ').upper()}",
        f"{MUSIC_SETTER:X} = {_jump(MUSIC_SETTER, ENTRY['music_setter'], 7).hex(' ').upper()}",
    ]
    for site, *_ in CONFIG_SITES:
        lines.append(f"{site:X} = {_jump(site, ENTRY[f'site_{site:x}'], 6).hex(' ').upper()}")
    for site, (_original, patched) in TABLE_SITE_BYTES.items():
        lines.append(f"{site:X} = {patched.hex(' ').upper()}")
    return "\n".join(lines + [""])


def verified_hooks() -> list[tuple[int, bytes]]:
    """Every site this tweak rewrites, with the bytes the game must have there."""
    hooks = [(TEXT_LOOKUP, TEXT_LOOKUP_ORIGINAL), (MUSIC_SETTER, MUSIC_SETTER_ORIGINAL),
             (TABLE, TABLE_ORIGINAL)]
    hooks += [(site, site_original(index, value, store)) for site, index, value, store in CONFIG_SITES]
    hooks += [(site, original) for site, (original, _patched) in TABLE_SITE_BYTES.items()]
    return hooks
