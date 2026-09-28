"""Hit-frame diagnostic log for issues #482 and #483.

Timed Hits and Timed Blocks need the moment each attack connects. The game
decides damage when the command resolves; the animation sequence shows it
later, and the instruction that does so is not yet identified statically
(see codex/ff8/timed-hits.md). This diagnostic watches it happen instead.

While enabled, every battle animation-sequence instruction the game runs is
appended to `lexeditor-hitframe.log` in the game folder as one line:

    <tsc hi><tsc lo> <sequence owner> <instruction address> <opcode> <HP 0> .. <HP 6> <motion>

`tsc` orders the lines in time. The owner is the sequence entity the engine
is running (`[01D98204]`). The seven HP values are battle participants 0-6
(three party members, four enemies), current HP at `01D27B28 + n x 0xD0`.
The first session's log (opcodes only) could not show which instruction is
the hit: owners interleave frame by frame and nothing marked the damage. With
HP on every line, the instruction on the line where a target's HP first
drops is the hit frame - or, if HP always drops before the attack animation
runs, that proves damage lands at the command and the display path is next.

The hook sits at the entry of the opcode handler `00504BB0`, which the
generic sequence interpreter `0050DB40` calls as `handler(opcode, &cursor)`
for every opcode below 0xC0. The hook replaces the handler's first two
instructions, runs them unchanged after logging, and resumes at `00504BB7`.
Off by default: with it off, no byte is written.

`motion` is the word at `01D97718`: one bit per animation object with an
active motion path. The physical-attack task releases the damage only once it
is 0 (codex/ff8/timed-hits.md, "What releases a hit"), so the log shows
whether a hit lands when the attacker's path ends - the time indicator needs
that to predict a hit before it lands. (Refuted: it was 0 at every hit.)

Task lines. The opcode stream above does not contain an attacker's swing:
the attacking model sits idle on its loop for seconds before its hit lands.
What drives an action is its task: the scheduler starts one per action
(0050A790) and it steps through states, starting numbered scripts with
00507080(id, model, ...) and waiting for them. Every task list runs through
00508420, which calls each task as [node + 8](node) at 00508433. The hook
there writes a line whenever a task's state byte (node + 0xD) changes or the
task finishes:

    <tsc> <task function> <task list> <new state, FF when finished> <HP ...> <motion>

and 00507080 writes one line per script it starts:

    <tsc> EEEEEEEE <script id> <model> <HP ...> <motion>

Next to the damage lines, these show which state and which script end at
the moment a hit lands, and how long they run.

Sequence lines. The 2026-09-28 log showed that an ordinary attack's damage
is applied as the swing starts, and the target flinches about 36 frames
later, just before the action ends. 00505C00(model, sequence) starts a
sequence on a model; the hook writes one line per call:

    <tsc> <model> <caller> <sequence id> <HP ...> <motion>

The caller column is a code address (00xxxxxx), unlike an opcode line's
script address. The line that starts the target's flinch names the code that
decides the moment of contact, which is where deferred damage must land.
"""

from __future__ import annotations

DEFAULT_HIT_FRAME_LOG = False

# FF8_EN.exe SHA-256 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570
HOOK = 0x00504BB0
HOOK_ORIGINAL = bytes.fromhex("8A 44 24 04 83 EC 08")  # mov al,[esp+4]; sub esp,8
HOOK_RESUME = 0x00504BB7
# 0048FE20(target) works out and applies one hit's damage. It runs from the
# action's queued battle task, mid-animation, so its lines mark when a hit
# lands: owner FFFFFFFF, the caller in the address column, the target index
# in the opcode column, then HP as on every line.
DAMAGE_HOOK = 0x0048FE20
DAMAGE_ORIGINAL = bytes.fromhex("83 EC 10 8B 44 24 14")  # sub esp,0x10; mov eax,[esp+0x14]
DAMAGE_RESUME = 0x0048FE27
DAMAGE_OWNER = 0xFFFFFFFF
SEQUENCE_OWNER = 0x01D98204
# 00508420(list) runs a task list: push esi; call [esi + 8]; add esp, 4.
TASK_HOOK = 0x00508433
TASK_ORIGINAL = bytes.fromhex("56 FF 56 08 83 C4 04")
TASK_RESUME = 0x0050843A
# 00507080(id, model, ...) starts a numbered script task.
SCRIPT_HOOK = 0x00507080
SCRIPT_ORIGINAL = bytes.fromhex("53 6A 01 6A 14")  # push ebx; push 1; push 0x14
SCRIPT_RESUME = 0x00507085
SCRIPT_OWNER = 0xEEEEEEEE
# 00505C00(model, sequence) starts a sequence on a model.
SEQUENCE_HOOK = 0x00505C00
SEQUENCE_ORIGINAL = bytes.fromhex("53 8B 5C 24 0C")  # push ebx; mov ebx, [esp+0xc]
SEQUENCE_RESUME = 0x00505C05

# Kernel32 import-table slots of the supported executable.
IAT_CREATE_FILE_A = 0x00B691C8
IAT_SET_FILE_POINTER = 0x00B691C4
IAT_WRITE_FILE = 0x00B690AC

# Unused cave range, above the ranges the other FF8 tweaks use.
CAVE = 0x027A9000
DATA = 0x027A9400
HANDLE = DATA + 0x00
WRITTEN = DATA + 0x04
HEX_DIGITS = DATA + 0x40
FILE_NAME = DATA + 0x60
LINE = DATA + 0x100  # up to 0x70 bytes: 39 + 7 x 9 + 2
LOG_NAME = "lexeditor-hitframe.log"
PARTICIPANT_HP = 0x01D27B28  # + participant x 0xD0
LOGGED_PARTICIPANTS = 7
MOTION_PATHS = 0x01D97718  # word: a bit per object whose motion path is running

ASSEMBLY = f"""
opcode:
    pushad
    pushfd
    mov esi, dword ptr [{SEQUENCE_OWNER:#x}]
    mov edx, dword ptr [esp + 44]
    mov edx, dword ptr [edx]
    dec edx
    movzx ecx, byte ptr [esp + 40]
    call write_line
    popfd
    popad
    mov al, byte ptr [esp + 4]
    sub esp, 8
    push {HOOK_RESUME:#x}
    ret
damage:
    pushad
    pushfd
    mov esi, {DAMAGE_OWNER:#x}
    mov edx, dword ptr [esp + 36]
    movzx ecx, byte ptr [esp + 40]
    call write_line
    popfd
    popad
    sub esp, 0x10
    mov eax, dword ptr [esp + 0x14]
    push {DAMAGE_RESUME:#x}
    ret
write_line:
    push ecx
    push edx
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
    je no_file
    push 2
    push 0
    push 0
    push eax
    call dword ptr [{IAT_SET_FILE_POINTER:#x}]
    mov eax, dword ptr [ebx]
have_handle:
    cmp eax, -1
    je no_file
    lea edi, [ebx + {LINE - DATA:#x}]
    rdtsc
    push eax
    mov eax, edx
    call hex8
    pop eax
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    mov eax, esi
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    pop eax
    call hex8
    mov byte ptr [edi], 0x20
    inc edi
    pop eax
    shl eax, 24
    mov ecx, 2
    call hexn
    xor esi, esi
hp_next:
    mov byte ptr [edi], 0x20
    inc edi
    imul eax, esi, 0xd0
    mov eax, dword ptr [eax + {PARTICIPANT_HP:#x}]
    call hex8
    inc esi
    cmp esi, {LOGGED_PARTICIPANTS}
    jb hp_next
    mov byte ptr [edi], 0x20
    inc edi
    movzx eax, word ptr [{MOTION_PATHS:#x}]
    shl eax, 16
    mov ecx, 4
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
    ret
no_file:
    add esp, 8
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
task:
    movzx edx, byte ptr [esi + 0xd]
    push edx
    push esi
    call dword ptr [esi + 8]
    add esp, 4
    pop edx
    pushad
    pushfd
    movzx ecx, byte ptr [esi + 0xd]
    test al, 2
    jz task_running
    mov ecx, 0xff
    jmp task_log
task_running:
    cmp ecx, edx
    je task_quiet
task_log:
    mov edx, ebp
    mov esi, dword ptr [esi + 8]
    call write_line
task_quiet:
    popfd
    popad
    push {TASK_RESUME:#x}
    ret
script:
    pushad
    pushfd
    mov esi, {SCRIPT_OWNER:#x}
    mov edx, dword ptr [esp + 0x28]
    movzx ecx, byte ptr [esp + 0x2c]
    call write_line
    popfd
    popad
    push ebx
    push 1
    push 0x14
    push {SCRIPT_RESUME:#x}
    ret
sequence:
    pushad
    pushfd
    mov esi, dword ptr [esp + 0x28]
    mov edx, dword ptr [esp + 0x24]
    movzx ecx, byte ptr [esp + 0x2c]
    call write_line
    popfd
    popad
    push ebx
    mov ebx, dword ptr [esp + 0xc]
    push {SEQUENCE_RESUME:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY (keystone); tests/ff8/test_ff8_hit_frame_log.py
# re-assembles it and runs it under unicorn to check the lines it writes.
CODE = bytes.fromhex(
    "60 9C 8B 35 04 82 D9 01 8B 54 24 2C 8B 12 4A 0F"
    "B6 4C 24 28 E8 33 00 00 00 9D 61 8A 44 24 04 83"
    "EC 08 68 B7 4B 50 00 C3 60 9C BE FF FF FF FF 8B"
    "54 24 24 0F B6 4C 24 28 E8 0F 00 00 00 9D 61 83"
    "EC 10 8B 44 24 14 68 27 FE 48 00 C3 51 52 BB 00"
    "94 7A 02 8B 03 85 C0 75 36 6A 00 68 80 00 00 00"
    "6A 04 6A 00 6A 01 68 00 00 00 40 8D 43 60 50 FF"
    "15 C8 91 B6 00 89 03 83 F8 FF 0F 84 AD 00 00 00"
    "6A 02 6A 00 6A 00 50 FF 15 C4 91 B6 00 8B 03 83"
    "F8 FF 0F 84 95 00 00 00 8D BB 00 01 00 00 0F 31"
    "50 89 D0 E8 89 00 00 00 58 E8 83 00 00 00 C6 07"
    "20 47 89 F0 E8 78 00 00 00 C6 07 20 47 58 E8 6E"
    "00 00 00 C6 07 20 47 58 C1 E0 18 B9 02 00 00 00"
    "E8 61 00 00 00 31 F6 C6 07 20 47 69 C6 D0 00 00"
    "00 8B 80 28 7B D2 01 E8 45 00 00 00 46 83 FE 07"
    "72 E5 C6 07 20 47 0F B7 05 18 77 D9 01 C1 E0 10"
    "B9 04 00 00 00 E8 2C 00 00 00 66 C7 07 0D 0A 83"
    "C7 02 6A 00 8D 43 04 50 8D 83 00 01 00 00 89 F9"
    "29 C1 51 50 FF 33 FF 15 AC 90 B6 00 C3 83 C4 08"
    "C3 B9 08 00 00 00 C1 C0 04 89 C2 83 E2 0F 8A 54"
    "13 40 88 17 47 49 75 EE C3 0F B6 56 0D 52 56 FF"
    "56 08 83 C4 04 5A 60 9C 0F B6 4E 0D A8 02 74 07"
    "B9 FF 00 00 00 EB 04 39 D1 74 0A 89 EA 8B 76 08"
    "E8 D7 FE FF FF 9D 61 68 3A 84 50 00 C3 60 9C BE"
    "EE EE EE EE 8B 54 24 28 0F B6 4C 24 2C E8 BA FE"
    "FF FF 9D 61 53 6A 01 6A 14 68 85 70 50 00 C3 60"
    "9C 8B 74 24 28 8B 54 24 24 0F B6 4C 24 2C E8 99"
    "FE FF FF 9D 61 53 8B 5C 24 0C 68 05 5C 50 00 C3"
)
ENTRY = {"opcode": 0x0, "damage": 0x28, "task": 0x149, "script": 0x17d, "sequence": 0x19f}

DATA_BYTES = (
    b"\x00" * 0x40
    + b"0123456789ABCDEF"
    + b"\x00" * 0x10
    + LOG_NAME.encode("ascii") + b"\x00"
)
DATA_BYTES += b"\x00" * (LINE - DATA + 0x80 - len(DATA_BYTES))


def _entry(name: str) -> int:
    # ENTRY records each entry point's offset in CODE (checked by the test).
    return CAVE + ENTRY[name]


def hook_bytes() -> bytes:
    jump = b"\xE9" + (_entry("opcode") - (HOOK + 5)).to_bytes(4, "little", signed=True)
    return jump + b"\x90" * (len(HOOK_ORIGINAL) - 5)


def damage_hook_bytes() -> bytes:
    jump = b"\xE9" + (_entry("damage") - (DAMAGE_HOOK + 5)).to_bytes(4, "little", signed=True)
    return jump + b"\x90" * (len(DAMAGE_ORIGINAL) - 5)


def task_hook_bytes() -> bytes:
    jump = b"\xE9" + (_entry("task") - (TASK_HOOK + 5)).to_bytes(4, "little", signed=True)
    return jump + b"\x90" * (len(TASK_ORIGINAL) - 5)


def script_hook_bytes() -> bytes:
    return b"\xE9" + (_entry("script") - (SCRIPT_HOOK + 5)).to_bytes(4, "little", signed=True)


def sequence_hook_bytes() -> bytes:
    return b"\xE9" + (_entry("sequence") - (SEQUENCE_HOOK + 5)).to_bytes(4, "little", signed=True)


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
        f"{DAMAGE_HOOK:X} = {damage_hook_bytes().hex(' ').upper()}",
        f"{TASK_HOOK:X} = {task_hook_bytes().hex(' ').upper()}",
        f"{SCRIPT_HOOK:X} = {script_hook_bytes().hex(' ').upper()}",
        f"{SEQUENCE_HOOK:X} = {sequence_hook_bytes().hex(' ').upper()}",
        "",
    ))
