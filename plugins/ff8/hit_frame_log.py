"""Hit-frame diagnostic log for issues #482 and #483.

Timed Hits and Timed Blocks need the moment each attack connects. The game
decides damage when the command resolves; the animation sequence shows it
later, and the instruction that does so is not yet identified statically
(see codex/ff8/timed-hits.md). This diagnostic watches it happen instead.

While enabled, every battle animation-sequence instruction the game runs is
appended to `lexeditor-hitframe.log` in the game folder as one line:

    <tsc hi><tsc lo> <sequence owner> <instruction address> <opcode>

`tsc` orders the lines in time. The owner is the sequence entity the engine
is running (`[01D98204]`). A hit shows as the target starting its
damage-taken sequence immediately after one of the attacker's instructions,
and that instruction is the hit frame.

The hook sits at the entry of the opcode handler `00504BB0`, which the
generic sequence interpreter `0050DB40` calls as `handler(opcode, &cursor)`
for every opcode below 0xC0. The hook replaces the handler's first two
instructions, runs them unchanged after logging, and resumes at `00504BB7`.
Off by default: with it off, no byte is written.
"""

from __future__ import annotations

DEFAULT_HIT_FRAME_LOG = False

# FF8_EN.exe SHA-256 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570
HOOK = 0x00504BB0
HOOK_ORIGINAL = bytes.fromhex("8A 44 24 04 83 EC 08")  # mov al,[esp+4]; sub esp,8
HOOK_RESUME = 0x00504BB7
SEQUENCE_OWNER = 0x01D98204

# Kernel32 import-table slots of the supported executable.
IAT_CREATE_FILE_A = 0x00B691C8
IAT_SET_FILE_POINTER = 0x00B691C4
IAT_WRITE_FILE = 0x00B690AC

# Unused cave range, above the ranges the other FF8 tweaks use.
CAVE = 0x027A9000
DATA = 0x027A9400
HANDLE = DATA + 0x00
WRITTEN = DATA + 0x04
LINE = DATA + 0x08
HEX_DIGITS = DATA + 0x40
FILE_NAME = DATA + 0x60
LOG_NAME = "lexeditor-hitframe.log"

ASSEMBLY = f"""
    pushad
    pushfd
    mov ebx, {DATA:#x}
    mov eax, dword ptr [ebx]
    test eax, eax
    jnz have_handle
    push 0
    push 0x80
    push 4
    push 0
    push 1
    push 0x40000000
    lea eax, [ebx + {FILE_NAME - DATA:#x}]
    push eax
    call dword ptr [{IAT_CREATE_FILE_A:#x}]
    mov dword ptr [ebx], eax
    cmp eax, -1
    je done
    push 2
    push 0
    push 0
    push eax
    call dword ptr [{IAT_SET_FILE_POINTER:#x}]
    mov eax, dword ptr [ebx]
have_handle:
    cmp eax, -1
    je done
    lea edi, [ebx + {LINE - DATA:#x}]
    rdtsc
    push eax
    mov eax, edx
    call hex8
    pop eax
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    mov eax, dword ptr [{SEQUENCE_OWNER:#x}]
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    mov eax, dword ptr [esp + 44]
    mov eax, dword ptr [eax]
    dec eax
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    movzx eax, byte ptr [esp + 40]
    shl eax, 24
    mov ecx, 2
    call hexn
    mov word ptr [edi], 0x0a0d
    add edi, 2
    push 0
    lea eax, [ebx + {WRITTEN - DATA:#x}]
    push eax
    lea eax, [ebx + {LINE - DATA:#x}]
    mov ecx, edi
    sub ecx, eax
    push ecx
    push eax
    push dword ptr [ebx]
    call dword ptr [{IAT_WRITE_FILE:#x}]
done:
    popfd
    popad
    mov al, byte ptr [esp + 4]
    sub esp, 8
    push {HOOK_RESUME:#x}
    ret
hex8:
    mov ecx, 8
hexn:
    rol eax, 4
    mov edx, eax
    and edx, 0xf
    mov dl, byte ptr [ebx + edx + {HEX_DIGITS - DATA:#x}]
    mov byte ptr [edi], dl
    inc edi
    dec ecx
    jnz hexn
    ret
"""

# Assembled at CAVE from ASSEMBLY (keystone); tests/ff8/test_ff8_hit_frame_log.py
# re-assembles it and runs it under unicorn to check the lines it writes.
CODE = bytes.fromhex(
    "60 9C BB 00 94 7A 02 8B 03 85 C0 75 32 6A 00 68"
    "80 00 00 00 6A 04 6A 00 6A 01 68 00 00 00 40 8D"
    "43 60 50 FF 15 C8 91 B6 00 89 03 83 F8 FF 74 7A"
    "6A 02 6A 00 6A 00 50 FF 15 C4 91 B6 00 8B 03 83"
    "F8 FF 74 66 8D 7B 08 0F 31 50 89 D0 E8 68 00 00"
    "00 58 E8 62 00 00 00 C6 07 20 47 A1 04 82 D9 01"
    "E8 54 00 00 00 C6 07 20 47 8B 44 24 2C 8B 00 48"
    "E8 44 00 00 00 C6 07 20 47 0F B6 44 24 28 C1 E0"
    "18 B9 02 00 00 00 E8 33 00 00 00 66 C7 07 0D 0A"
    "83 C7 02 6A 00 8D 43 04 50 8D 43 08 89 F9 29 C1"
    "51 50 FF 33 FF 15 AC 90 B6 00 9D 61 8A 44 24 04"
    "83 EC 08 68 B7 4B 50 00 C3 B9 08 00 00 00 C1 C0"
    "04 89 C2 83 E2 0F 8A 54 13 40 88 17 47 49 75 EE"
    "C3"
)

DATA_BYTES = (
    b"\x00" * 0x40
    + b"0123456789ABCDEF"
    + b"\x00" * 0x10
    + LOG_NAME.encode("ascii") + b"\x00"
)


def hook_bytes() -> bytes:
    jump = b"\xE9" + (CAVE - (HOOK + 5)).to_bytes(4, "little", signed=True)
    return jump + b"\x90" * (len(HOOK_ORIGINAL) - 5)


def build_hext(enabled: bool) -> str:
    """Return the diagnostic's Hext fragment, or nothing when it is off."""
    if not isinstance(enabled, bool):
        raise ValueError("Hit-frame log must be true or false")
    if not enabled:
        return ""
    return "\n".join((
        f"# Hit-frame log (#482/#483): battle animation instructions -> {LOG_NAME}.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{DATA:X}:{len(DATA_BYTES):X}",
        f"{DATA:X} = {DATA_BYTES.hex(' ').upper()}",
        f"{HOOK:X} = {hook_bytes().hex(' ').upper()}",
        "",
    ))
