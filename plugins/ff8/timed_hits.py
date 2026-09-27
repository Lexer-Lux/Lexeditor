"""Timed Hits and Timed Blocks for every character (#482, #483), as Hext.

Lexer's rule (2026-09-27): one timing system for everyone, Squall included,
and the press decides the hit (Lexer's redesign, 2026-09-27):

- The input window W is the longest time before a hit lands in which a press
  can succeed. The attack's own hit chance, from whichever formula is active,
  sets the hit window: 75% hit chance gives 0.75 W before the hit lands.
- The attack's own crit chance sets the crit window, as a share of the hit
  window: 50% crit chance with that 0.75 W gives the last 0.375 W.
- A press inside the hit window hits; inside the crit window it crits. A
  press outside it, or no press at all, misses. The window is only before the
  hit: a press after it lands does nothing.
- Only a party member's attack on an enemy is decided this way. An enemy's
  hit on a party member is a timed block: a press inside W before it lands
  cuts the damage taken to the block percentage.

One press, at the right time (Lexer, 2026-09-26: mashing Square won every hit):

- The first press arms the next hit. A second press while it is armed is a
  fumble: the miss sound plays at once, and that hit misses. Mashing on keeps
  the fumble going silently until the player lets up for three windows
  (Lexer, 2026-09-27: mashing with Squall was silent until the hit, then
  sounded two or three times).
- A press more than three windows before the hit is forgotten.
- A press after a hit lands counts for nothing on that hit: it arms the
  next one. So the hits of a multi-hit attack can each be timed, however
  close together they land.

Against FF8_EN.exe SHA-256 064d466b...9570 (see codex/ff8/timed-hits.md):

- Presses: the battle input routine 004A84E0 stores this frame's newly
  pressed buttons at [01D6D490] + 0x12. The hook at 004A8554 records
  timeGetTime (import 00B69378) when bit 0x80 (Square) is newly pressed.
- Physical attacks (damage types 1 and the others routed through 00492B00):
  00492B00 decides an automatic hit (hit rate 255, or a sleeping or stopped
  target), 00492BA0 rolls the hit and 00492B30 rolls the crit, each by
  comparing a 0-255 threshold with the game's random byte (0048F020). The
  threshold is whatever the active formula made it, so Formulae Rework's
  accuracy counts. The hook replaces the random byte with the verdict: 0 to
  land, or a zeroed threshold to fail. An automatic hit is a 100% hit chance.
- Types 34 and 36 go to 00492E10 instead, which rolls the same way with the
  threshold in EDI, the attacker x 0xD0 in ESI and the target x 0xD0 in EBP.
  Full LUCK Accuracy changes this routine's threshold only. Its automatic hit
  skips the hit roll and only rolls the crit (00492EA3), so a miss there
  returns into the routine's own miss exit, 004930CB, which sets the miss
  mark and deals nothing.
- Squall's gunblade (type 10, 0048F480) never rolls: its hit chance is 100%.
  His hit lands through 00485160 when his own trigger window closes; only
  that call, with the hit counter 01D28D90 set, is judged. A miss takes the
  handler's own no-damage exit with the miss mark (01D27ADE bit 4); a crit
  sets the crit flag 01D28E07, which the handler doubles at 0048F652, and
  the crit mark (bit 2). The crit threshold is the one 00492B30 uses:
  (attacker LUCK + the attack's crit bonus 01D2A23B) x 255 / 256.
- Blocks: at 00491124, just before the damage cap, ESI is the hit's damage,
  the attacker is byte 01D27AD8 and [esp+0x10] is the target x 0xD0.
- Physical only (option, off by default) limits blocks to physical hits: the
  entry of 004922B0(type, ...) records the kernel attack type.
- Squall's own gunblade trigger bonus is switched off: the two stores to its
  quality word 01D28D94 (00485158, 004851D6) no longer write.
- Sounds play through 0046B280(sound); the number is the audio.fmt index
  shown on the SFX tab.
"""

from __future__ import annotations

DEFAULT_TIMED_HITS = False
DEFAULT_WINDOW_MS = 500
MIN_WINDOW_MS = 50
MAX_WINDOW_MS = 2000
DEFAULT_BLOCK_PERCENT = 50  # share of the damage a timed block still takes
MIN_BLOCK_PERCENT = 0
MAX_BLOCK_PERCENT = 100
DEFAULT_SUCCESS_SOUND = 1   # the menu confirm sound (menu sounds 1 and 2)
DEFAULT_CRIT_SOUND = 9      # menu sound 3 in the table at 00B87D28
DEFAULT_FAILURE_SOUND = 16  # the menu denied buzz (menu sound 5)
MAX_SOUND = 2790            # audio.fmt holds 2791 entries; 0 is blank
EARLY_FACTOR = 3            # a press older than 3 windows is forgotten
DEFAULT_PHYSICAL_ONLY = False

INPUT_HOOK = 0x004A8554
INPUT_ORIGINAL = bytes.fromhex("66 8B 41 10 66 89 41 18")
INPUT_RESUME = 0x004A855C
BATTLE_INPUT = 0x01D6D490   # pointer; +0x12 newly pressed
SQUARE = 0x80  # FF8 function bits: L2 01 R2 02 L1 04 R1 08 Tri 10 O 20 X 40 Sq 80
HIT_HOOK = 0x00491124
HIT_ORIGINAL = bytes.fromhex("8A 0D 0E 8E D2 01")  # mov cl, [01D28E0E]
HIT_RESUME = 0x0049112A
TYPE_HOOK = 0x004922B0
TYPE_ORIGINAL = bytes.fromhex("A0 0E 8E D2 01")  # mov al, [01D28E0E]
TYPE_RESUME = 0x004922B5
AUTO_HOOK = 0x00492B22
AUTO_ORIGINAL = bytes.fromhex("B8 01 00 00 00 C3")  # mov eax, 1; ret
HIT_ROLL_CALL = 0x00492C15
CRIT_ROLL_CALL = 0x00492B6C
RANDOM = 0x0048F020
E10_AUTO_CRIT_CALL = 0x00492EA3
E10_HIT_ROLL_CALL = 0x00492F29
E10_CRIT_ROLL_CALL = 0x00492F71
E10_MISS = 0x004930CB
PARTY_OFFSET = 3 * 0xD0     # participant offsets below this are the party
GUNBLADE_HOOK = 0x0048F530
GUNBLADE_ORIGINAL = bytes.fromhex("53 33 DB 8D 44 95 00")  # push ebx; xor ebx,ebx; lea eax,[ebp+edx*4]
GUNBLADE_RESUME = 0x0048F537
GUNBLADE_NO_DAMAGE = 0x0048F522  # xor eax, eax; pop ebp; ret
PHYSICAL_TYPES = (1, 7, 9, 10, 36)
PHYSICAL_MASK = sum(1 << kind for kind in PHYSICAL_TYPES if kind < 32)
PHYSICAL_HIGH = tuple(kind for kind in PHYSICAL_TYPES if kind >= 32)
ATTACKER = 0x01D27AD8
PARTICIPANTS = 0x01D27B10   # + index x 0xD0
LUCK = 0xC2                 # participant byte: LUCK (01D27BD2 - 01D27B10)
CRIT_BONUS = 0x01D2A23B
HIT_COUNTER = 0x01D28D90    # set only while 00485160 lands a trigger hit
CRIT_FLAG = 0x01D28E07
HIT_MARKS = 0x01D27ADE      # bit 2 crit, bit 4 miss
PARTY_SIZE = 3
TIME_GET_TIME = 0x00B69378  # IAT slot
PLAY_SOUND = 0x0046B280
TRIGGER_STORES = (
    (0x00485158, bytes.fromhex("66 A3 94 8D D2 01"), bytes.fromhex("90 90 90 90 90 90")),
    (0x004851D6, bytes.fromhex("66 C7 05 94 8D D2 01 01 00"),
     bytes.fromhex("66 C7 05 94 8D D2 01 00 00")),
)

CAVE = 0x027AB900
# Settings live in data beside the code, so the code is fixed and embedded
# and a mod's settings only change these bytes.
DATA = 0x027ABE00
WINDOW = DATA + 0x00
EARLY = DATA + 0x04
BLOCK = DATA + 0x08
SOUND_SUCCESS = DATA + 0x0C
SOUND_CRIT = DATA + 0x10
SOUND_FAILURE = DATA + 0x14
PRESS_TIME = DATA + 0x18
PRESSED = DATA + 0x1C
PHYSICAL_ONLY = DATA + 0x20
HIT_TYPE = DATA + 0x24
LAST_HIT = DATA + 0x28      # time the last judged hit landed
FUMBLED = DATA + 0x2C       # a second press arrived while armed
RESERVED = DATA + 0x30
JUDGED = DATA + 0x34        # the judged press's lead over its hit, or -1
HIT_WINDOW = DATA + 0x38    # that hit's window, for its crit window
FORCE_MISS = DATA + 0x3C    # an automatic hit that missed: fail the roll after it
DATA_SIZE = 0x40

ASSEMBLY = f"""
input:
    mov ax, word ptr [ecx + 0x10]
    mov word ptr [ecx + 0x18], ax
    test byte ptr [ecx + 0x12], {SQUARE:#x}
    jz input_done
    pushad
    call dword ptr [{TIME_GET_TIME:#x}]
    cmp dword ptr [{PRESSED:#x}], 0
    je arm
    mov edx, eax
    sub edx, dword ptr [{PRESS_TIME:#x}]
    cmp edx, dword ptr [{EARLY:#x}]
    ja arm
    mov dword ptr [{PRESS_TIME:#x}], eax
    cmp dword ptr [{FUMBLED:#x}], 0
    jne input_popped
    mov dword ptr [{FUMBLED:#x}], 1
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    jmp input_popped
arm:
    mov dword ptr [{PRESS_TIME:#x}], eax
    mov dword ptr [{PRESSED:#x}], 1
    mov dword ptr [{FUMBLED:#x}], 0
input_popped:
    popad
input_done:
    push {INPUT_RESUME:#x}
    ret

verdict:
    push ebx
    push ecx
    push edx
    mov ebx, dword ptr [esp + 0x10]
    cmp ebx, 255
    jbe verdict_clamped
    mov ebx, 255
verdict_clamped:
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{LAST_HIT:#x}], eax
    mov dword ptr [{JUDGED:#x}], 0xffffffff
    cmp dword ptr [{PRESSED:#x}], 0
    je verdict_miss
    mov dword ptr [{PRESSED:#x}], 0
    mov ecx, eax
    sub ecx, dword ptr [{PRESS_TIME:#x}]
    cmp ecx, dword ptr [{EARLY:#x}]
    ja verdict_miss
    cmp dword ptr [{FUMBLED:#x}], 0
    jne verdict_miss
    mov eax, dword ptr [{WINDOW:#x}]
    mul ebx
    push ecx
    mov ecx, 255
    div ecx
    pop ecx
    test ebx, ebx
    jz verdict_miss_sound
    cmp ecx, eax
    ja verdict_miss_sound
    mov dword ptr [{HIT_WINDOW:#x}], eax
    mov dword ptr [{JUDGED:#x}], ecx
    mov eax, 1
    jmp verdict_done
verdict_miss_sound:
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
verdict_miss:
    xor eax, eax
verdict_done:
    pop edx
    pop ecx
    pop ebx
    ret

crit:
    push ebx
    push ecx
    push edx
    mov ebx, dword ptr [esp + 0x10]
    cmp ebx, 255
    jbe crit_clamped
    mov ebx, 255
crit_clamped:
    mov ecx, dword ptr [{JUDGED:#x}]
    cmp ecx, 0xffffffff
    je crit_none
    mov dword ptr [{JUDGED:#x}], 0xffffffff
    mov eax, dword ptr [{HIT_WINDOW:#x}]
    mul ebx
    push ecx
    mov ecx, 255
    div ecx
    pop ecx
    test ebx, ebx
    jz crit_plain
    cmp ecx, eax
    ja crit_plain
    push dword ptr [{SOUND_CRIT:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    mov eax, 1
    jmp crit_done
crit_plain:
    push dword ptr [{SOUND_SUCCESS:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
crit_none:
    xor eax, eax
crit_done:
    pop edx
    pop ecx
    pop ebx
    ret

auto:
    cmp dword ptr [esp + 4], {PARTY_SIZE}
    jae auto_hit
    cmp dword ptr [esp + 8], {PARTY_SIZE}
    jb auto_hit
    push 255
    call verdict
    add esp, 4
    test eax, eax
    jnz auto_done
    mov dword ptr [{FORCE_MISS:#x}], 1
    ret
auto_hit:
    mov eax, 1
auto_done:
    ret

hit_roll:
    cmp dword ptr [esp + 0xc], {PARTY_SIZE}
    jae real_random
    cmp dword ptr [esp + 0x10], {PARTY_SIZE}
    jb real_random
    cmp dword ptr [{FORCE_MISS:#x}], 0
    je hit_roll_judge
    mov dword ptr [{FORCE_MISS:#x}], 0
    xor esi, esi
    ret
hit_roll_judge:
    push esi
    call verdict
    add esp, 4
    test eax, eax
    jz roll_fails
    xor eax, eax
    ret
roll_fails:
    xor esi, esi
    ret
real_random:
    jmp {RANDOM:#x}

crit_roll:
    cmp dword ptr [esp + 0xc], {PARTY_SIZE}
    jae real_random
    cmp dword ptr [esp + 0x10], {PARTY_SIZE}
    jb real_random
    push esi
    call crit
    add esp, 4
    test eax, eax
    jz roll_fails
    xor eax, eax
    ret

e10_hit_roll:
    cmp esi, {PARTY_OFFSET:#x}
    jae real_random
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push edi
    call verdict
    add esp, 4
    test eax, eax
    jz e10_fails
    xor eax, eax
    ret
e10_fails:
    xor edi, edi
    ret

e10_crit_roll:
    cmp esi, {PARTY_OFFSET:#x}
    jae real_random
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push edi
    call crit
    add esp, 4
    test eax, eax
    jz e10_fails
    xor eax, eax
    ret

e10_auto_crit:
    cmp esi, {PARTY_OFFSET:#x}
    jae real_random
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push 255
    call verdict
    add esp, 4
    test eax, eax
    jnz e10_crit_roll
    mov dword ptr [esp], {E10_MISS:#x}
    ret

gunblade:
    pushad
    pushfd
    cmp dword ptr [esp + 0x2c], {PARTY_SIZE}
    jae gunblade_resume
    cmp ebp, {PARTY_SIZE}
    jb gunblade_resume
    cmp word ptr [{HIT_COUNTER:#x}], 0
    je gunblade_resume
    push 255
    call verdict
    add esp, 4
    test eax, eax
    jz gunblade_miss
    mov eax, dword ptr [esp + 0x2c]
    imul eax, eax, 0xd0
    movzx eax, byte ptr [eax + {PARTICIPANTS + LUCK:#x}]
    movzx ecx, byte ptr [{CRIT_BONUS:#x}]
    add eax, ecx
    imul eax, eax, 255
    shr eax, 8
    push eax
    call crit
    add esp, 4
    test eax, eax
    jz gunblade_resume
    mov byte ptr [{CRIT_FLAG:#x}], 1
    or byte ptr [{HIT_MARKS:#x}], 2
gunblade_resume:
    popfd
    popad
    push ebx
    xor ebx, ebx
    lea eax, [ebp + edx*4]
    push {GUNBLADE_RESUME:#x}
    ret
gunblade_miss:
    popfd
    popad
    or byte ptr [{HIT_MARKS:#x}], 4
    push {GUNBLADE_NO_DAMAGE:#x}
    ret

hit:
    pushad
    pushfd
    test esi, esi
    jle hit_done
    cmp dword ptr [{PHYSICAL_ONLY:#x}], 0
    je typed
    movzx eax, byte ptr [{HIT_TYPE:#x}]
    cmp eax, {PHYSICAL_HIGH[0]}
    je typed
    cmp eax, 31
    ja hit_done
    mov ecx, {PHYSICAL_MASK:#x}
    bt ecx, eax
    jnc hit_done
typed:
    movzx ebx, byte ptr [{ATTACKER:#x}]
    cmp ebx, {PARTY_SIZE}
    jb hit_done
    mov eax, dword ptr [esp + 0x34]
    xor edx, edx
    mov ecx, 0xd0
    div ecx
    cmp eax, {PARTY_SIZE}
    jae hit_done
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{LAST_HIT:#x}], eax
    cmp dword ptr [{PRESSED:#x}], 0
    je hit_done
    mov dword ptr [{PRESSED:#x}], 0
    sub eax, dword ptr [{PRESS_TIME:#x}]
    cmp eax, dword ptr [{EARLY:#x}]
    ja hit_done
    cmp dword ptr [{FUMBLED:#x}], 0
    jne hit_done
    cmp eax, dword ptr [{WINDOW:#x}]
    ja block_missed
    mov eax, dword ptr [esp + 8]
    imul eax, dword ptr [{BLOCK:#x}]
    xor edx, edx
    mov ecx, 100
    div ecx
    mov dword ptr [esp + 8], eax
    push dword ptr [{SOUND_SUCCESS:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    jmp hit_done
block_missed:
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
hit_done:
    popfd
    popad
    mov cl, byte ptr [0x1d28e0e]
    push {HIT_RESUME:#x}
    ret

hit_type:
    mov eax, dword ptr [esp + 4]
    mov byte ptr [{HIT_TYPE:#x}], al
    mov al, byte ptr [0x1d28e0e]
    push {TYPE_RESUME:#x}
    ret
"""

ENTRY_LABELS = ("hit", "hit_type", "auto", "hit_roll", "crit_roll", "gunblade",
                "e10_hit_roll", "e10_crit_roll", "e10_auto_crit")

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_timed_hits.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "66 8B 41 10 66 89 41 18 F6 41 12 80 74 62 60 FF"
    "15 78 93 B6 00 83 3D 1C BE 7A 02 00 74 38 89 C2"
    "2B 15 18 BE 7A 02 3B 15 04 BE 7A 02 77 28 A3 18"
    "BE 7A 02 83 3D 2C BE 7A 02 00 75 33 C7 05 2C BE"
    "7A 02 01 00 00 00 FF 35 14 BE 7A 02 E8 2F F9 CB"
    "FD 83 C4 04 EB 19 A3 18 BE 7A 02 C7 05 1C BE 7A"
    "02 01 00 00 00 C7 05 2C BE 7A 02 00 00 00 00 61"
    "68 5C 85 4A 00 C3 53 51 52 8B 5C 24 10 81 FB FF"
    "00 00 00 76 05 BB FF 00 00 00 FF 15 78 93 B6 00"
    "A3 28 BE 7A 02 C7 05 34 BE 7A 02 FF FF FF FF 83"
    "3D 1C BE 7A 02 00 74 5B C7 05 1C BE 7A 02 00 00"
    "00 00 89 C1 2B 0D 18 BE 7A 02 3B 0D 04 BE 7A 02"
    "77 41 83 3D 2C BE 7A 02 00 75 38 A1 00 BE 7A 02"
    "F7 E3 51 B9 FF 00 00 00 F7 F1 59 85 DB 74 16 39"
    "C1 77 12 A3 38 BE 7A 02 89 0D 34 BE 7A 02 B8 01"
    "00 00 00 EB 10 FF 35 14 BE 7A 02 E8 80 F8 CB FD"
    "83 C4 04 31 C0 5A 59 5B C3 53 51 52 8B 5C 24 10"
    "81 FB FF 00 00 00 76 05 BB FF 00 00 00 8B 0D 34"
    "BE 7A 02 83 F9 FF 74 45 C7 05 34 BE 7A 02 FF FF"
    "FF FF A1 38 BE 7A 02 F7 E3 51 B9 FF 00 00 00 F7"
    "F1 59 85 DB 74 19 39 C1 77 15 FF 35 10 BE 7A 02"
    "E8 2B F8 CB FD 83 C4 04 B8 01 00 00 00 EB 10 FF"
    "35 0C BE 7A 02 E8 16 F8 CB FD 83 C4 04 31 C0 5A"
    "59 5B C3 83 7C 24 04 03 73 23 83 7C 24 08 03 72"
    "1C 68 FF 00 00 00 E8 EB FE FF FF 83 C4 04 85 C0"
    "75 10 C7 05 3C BE 7A 02 01 00 00 00 C3 B8 01 00"
    "00 00 C3 83 7C 24 0C 03 73 30 83 7C 24 10 03 72"
    "29 83 3D 3C BE 7A 02 00 74 0D C7 05 3C BE 7A 02"
    "00 00 00 00 31 F6 C3 56 E8 A9 FE FF FF 83 C4 04"
    "85 C0 74 03 31 C0 C3 31 F6 C3 E9 41 35 CE FD 83"
    "7C 24 0C 03 73 F4 83 7C 24 10 03 72 ED 56 E8 16"
    "FF FF FF 83 C4 04 85 C0 74 DD 31 C0 C3 81 FE 70"
    "02 00 00 73 D5 81 FD 70 02 00 00 72 CD 57 E8 63"
    "FE FF FF 83 C4 04 85 C0 74 03 31 C0 C3 31 FF C3"
    "81 FE 70 02 00 00 73 B2 81 FD 70 02 00 00 72 AA"
    "57 E8 D3 FE FF FF 83 C4 04 85 C0 74 E0 31 C0 C3"
    "81 FE 70 02 00 00 73 92 81 FD 70 02 00 00 72 8A"
    "68 FF 00 00 00 E8 1C FE FF FF 83 C4 04 85 C0 75"
    "BF C7 04 24 CB 30 49 00 C3 60 9C 83 7C 24 2C 03"
    "73 5E 83 FD 03 72 59 66 83 3D 90 8D D2 01 00 74"
    "4F 68 FF 00 00 00 E8 EB FD FF FF 83 C4 04 85 C0"
    "74 4D 8B 44 24 2C 69 C0 D0 00 00 00 0F B6 80 D2"
    "7B D2 01 0F B6 0D 3B A2 D2 01 01 C8 69 C0 FF 00"
    "00 00 C1 E8 08 50 E8 4E FE FF FF 83 C4 04 85 C0"
    "74 0E C6 05 07 8E D2 01 01 80 0D DE 7A D2 01 02"
    "9D 61 53 31 DB 8D 44 95 00 68 37 F5 48 00 C3 9D"
    "61 80 0D DE 7A D2 01 04 68 22 F5 48 00 C3 60 9C"
    "85 F6 0F 8E C1 00 00 00 83 3D 20 BE 7A 02 00 74"
    "23 0F B6 05 24 BE 7A 02 83 F8 24 74 17 83 F8 1F"
    "0F 87 A3 00 00 00 B9 82 06 00 00 0F A3 C1 0F 83"
    "95 00 00 00 0F B6 1D D8 7A D2 01 83 FB 03 0F 82"
    "85 00 00 00 8B 44 24 34 31 D2 B9 D0 00 00 00 F7"
    "F1 83 F8 03 73 73 FF 15 78 93 B6 00 A3 28 BE 7A"
    "02 83 3D 1C BE 7A 02 00 74 5F C7 05 1C BE 7A 02"
    "00 00 00 00 2B 05 18 BE 7A 02 3B 05 04 BE 7A 02"
    "77 47 83 3D 2C BE 7A 02 00 75 3E 3B 05 00 BE 7A"
    "02 77 28 8B 44 24 08 0F AF 05 08 BE 7A 02 31 D2"
    "B9 64 00 00 00 F7 F1 89 44 24 08 FF 35 0C BE 7A"
    "02 E8 DA F5 CB FD 83 C4 04 EB 0E FF 35 14 BE 7A"
    "02 E8 CA F5 CB FD 83 C4 04 9D 61 8A 0D 0E 8E D2"
    "01 68 2A 11 49 00 C3 8B 44 24 04 A2 24 BE 7A 02"
    "A0 0E 8E D2 01 68 B5 22 49 00 C3"
)
ENTRIES = {
    "hit": 0x27abbee,
    "hit_type": 0x27abcc7,
    "auto": 0x27aba73,
    "hit_roll": 0x27abaa3,
    "crit_roll": 0x27abadf,
    "gunblade": 0x27abb69,
    "e10_hit_roll": 0x27abafd,
    "e10_crit_roll": 0x27abb20,
    "e10_auto_crit": 0x27abb40,
}
HIT_ENTRY = ENTRIES.get("hit", 0)
TYPE_ENTRY = ENTRIES.get("hit_type", 0)


def _assemble() -> tuple[bytes, dict]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])

    def entry(label: str) -> int:
        probe = ASSEMBLY.split(f"\n{label}:")[0] + f"\n{label}:\n nop"
        return CAVE + len(ks.asm(probe, CAVE)[0]) - 1
    return code, {label: entry(label) for label in ENTRY_LABELS}


def _bounded(value, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number from {low} to {high}")
    if not low <= value <= high:
        raise ValueError(f"{label} must be from {low} to {high}")
    return value


def data_bytes(window_ms: int, block_percent: int, success_sound: int, crit_sound: int,
               failure_sound: int, physical_only: bool = False) -> bytes:
    values = (window_ms, window_ms * EARLY_FACTOR, block_percent, success_sound, crit_sound,
              failure_sound, 0, 0, int(physical_only), 0, 0, 0, 0, 0xFFFFFFFF, 0, 0)
    return b"".join(value.to_bytes(4, "little") for value in values)


def _jump(site: int, target: int, length: int) -> bytes:
    rel = (target - (site + 5)).to_bytes(4, "little", signed=True)
    return b"\xE9" + rel + b"\x90" * (length - 5)


def _call(site: int, target: int) -> bytes:
    return b"\xE8" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def build_hext(enabled: bool, *, window_ms: int = DEFAULT_WINDOW_MS,
               block_percent: int = DEFAULT_BLOCK_PERCENT,
               success_sound: int = DEFAULT_SUCCESS_SOUND,
               crit_sound: int = DEFAULT_CRIT_SOUND,
               failure_sound: int = DEFAULT_FAILURE_SOUND,
               physical_only: bool = DEFAULT_PHYSICAL_ONLY) -> str:
    """The patch with the chosen settings in its data, or nothing when off."""
    if not isinstance(enabled, bool):
        raise ValueError("Timed Hits must be true or false")
    if not isinstance(physical_only, bool):
        raise ValueError("Timed Hits physical only must be true or false")
    window_ms = _bounded(window_ms, MIN_WINDOW_MS, MAX_WINDOW_MS, "Timed Hits input window")
    block_percent = _bounded(block_percent, MIN_BLOCK_PERCENT, MAX_BLOCK_PERCENT, "Timed Blocks damage")
    success_sound = _bounded(success_sound, 1, MAX_SOUND, "Timed Hits hit sound")
    crit_sound = _bounded(crit_sound, 1, MAX_SOUND, "Timed Hits crit sound")
    failure_sound = _bounded(failure_sound, 1, MAX_SOUND, "Timed Hits miss sound")
    if not enabled:
        return ""
    data = data_bytes(window_ms, block_percent, success_sound, crit_sound, failure_sound, physical_only)
    lines = [
        f"# Timed Hits and Blocks: Square decides the hit within {window_ms} ms x hit chance before it "
        f"lands, and the crit within that x crit chance; blocks take {block_percent}%"
        f"{' (physical attacks only)' if physical_only else ''}.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{DATA:X}:{DATA_SIZE:X}",
        f"{DATA:X} = {data.hex(' ').upper()}",
        f"{INPUT_HOOK:X} = {_jump(INPUT_HOOK, CAVE, len(INPUT_ORIGINAL)).hex(' ').upper()}",
        f"{HIT_HOOK:X} = {_jump(HIT_HOOK, ENTRIES['hit'], len(HIT_ORIGINAL)).hex(' ').upper()}",
        f"{TYPE_HOOK:X} = {_jump(TYPE_HOOK, ENTRIES['hit_type'], len(TYPE_ORIGINAL)).hex(' ').upper()}",
        f"{AUTO_HOOK:X} = {_jump(AUTO_HOOK, ENTRIES['auto'], len(AUTO_ORIGINAL)).hex(' ').upper()}",
        f"{HIT_ROLL_CALL:X} = {_call(HIT_ROLL_CALL, ENTRIES['hit_roll']).hex(' ').upper()}",
        f"{CRIT_ROLL_CALL:X} = {_call(CRIT_ROLL_CALL, ENTRIES['crit_roll']).hex(' ').upper()}",
        f"{E10_AUTO_CRIT_CALL:X} = {_call(E10_AUTO_CRIT_CALL, ENTRIES['e10_auto_crit']).hex(' ').upper()}",
        f"{E10_HIT_ROLL_CALL:X} = {_call(E10_HIT_ROLL_CALL, ENTRIES['e10_hit_roll']).hex(' ').upper()}",
        f"{E10_CRIT_ROLL_CALL:X} = {_call(E10_CRIT_ROLL_CALL, ENTRIES['e10_crit_roll']).hex(' ').upper()}",
        f"{GUNBLADE_HOOK:X} = {_jump(GUNBLADE_HOOK, ENTRIES['gunblade'], len(GUNBLADE_ORIGINAL)).hex(' ').upper()}",
        "# Squall's own trigger bonus is off; he uses the same window as everyone.",
    ]
    for site, _original, patched in TRIGGER_STORES:
        lines.append(f"{site:X} = {patched.hex(' ').upper()}")
    return "\n".join(lines + [""])


SETTING_KEYS = {
    # settings key: (build_hext argument, default, minimum, maximum, label)
    "timedHitsWindow": ("window_ms", DEFAULT_WINDOW_MS, MIN_WINDOW_MS, MAX_WINDOW_MS, "Timed Hits input window"),
    "timedBlocksDamage": ("block_percent", DEFAULT_BLOCK_PERCENT, MIN_BLOCK_PERCENT, MAX_BLOCK_PERCENT, "Timed Blocks damage"),
    "timedHitsSuccessSound": ("success_sound", DEFAULT_SUCCESS_SOUND, 1, MAX_SOUND, "Timed Hits hit sound"),
    "timedHitsCritSound": ("crit_sound", DEFAULT_CRIT_SOUND, 1, MAX_SOUND, "Timed Hits crit sound"),
    "timedHitsFailureSound": ("failure_sound", DEFAULT_FAILURE_SOUND, 1, MAX_SOUND, "Timed Hits miss sound"),
    "timedHitsPhysicalOnly": ("physical_only", DEFAULT_PHYSICAL_ONLY, False, True, "Timed Hits physical only"),
}


def options(data: dict, *, strict: bool) -> dict:
    """The settings from a settings document, as build_hext arguments.

    Loading is forgiving (a bad stored value falls back to its default);
    saving is strict and names the value that is out of range.
    """
    result = {}
    for key, (argument, default, low, high, label) in SETTING_KEYS.items():
        value = data.get(key, default)
        if isinstance(default, bool):
            if isinstance(value, bool):
                result[argument] = value
            elif strict:
                raise ValueError(f"{label} must be true or false")
            else:
                result[argument] = default
            continue
        try:
            result[argument] = _bounded(value, low, high, label)
        except ValueError:
            if strict:
                raise
            result[argument] = default
    return result


def limits() -> dict:
    """Defaults and bounds for the editor's controls."""
    return {key: {"default": default, "minimum": low, "maximum": high}
            for key, (_argument, default, low, high, _label) in SETTING_KEYS.items()
            if not isinstance(default, bool)}


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(INPUT_HOOK, INPUT_ORIGINAL), (HIT_HOOK, HIT_ORIGINAL), (TYPE_HOOK, TYPE_ORIGINAL),
            (AUTO_HOOK, AUTO_ORIGINAL), (GUNBLADE_HOOK, GUNBLADE_ORIGINAL),
            *((site, _call(site, RANDOM)) for site in (HIT_ROLL_CALL, CRIT_ROLL_CALL, E10_AUTO_CRIT_CALL,
                                                       E10_HIT_ROLL_CALL, E10_CRIT_ROLL_CALL)),
            *((site, original) for site, original, _ in TRIGGER_STORES)]
