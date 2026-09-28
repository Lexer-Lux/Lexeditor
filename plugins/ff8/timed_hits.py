"""Timed Hits and Timed Blocks for every character (#482, #483), as Hext.

Lexer's rule (2026-09-27): one timing system for everyone, Squall included,
and the press decides the outcome. W is the input window setting.

Attacks (a party member's hit on an enemy):

- The attack's own hit chance, from whichever formula is active, sets the
  hit window: W x hit chance before the hit lands. Its crit chance sets the
  crit window, the last part of the hit window: hit window x crit chance.
  W 1000 ms, 75% and 50%: a press in the last 750 ms hits, in the last
  375 ms it crits. Earlier, or no press, misses. A press after the hit lands
  does nothing for it.

Blocks (an enemy's hit on a party member), the same bands inverted:

- The last W x (1 - hit chance) before the hit is a dodge: the enemy misses.
  Before that, W x hit chance x (1 - crit chance) is a normal hit, and the
  rest of W is a crit. No press, or a press before W, is the worst band there
  is: a crit, or a normal hit when the attack cannot crit. W 1000 ms, 20% and
  50%: the last 800 ms dodges, the 100 ms before that is a normal hit, the
  100 ms before that crits.

Continuous grading (option): the bands stay, and the damage inside them is
graded by the timing. An attack's damage rises from 0 where its hit window
opens to normal damage where its crit window opens, then to crit damage at
the moment of the hit. A block mirrors it: the damage taken is 0 at the edge
of the dodge band, normal at the far edge of the normal band, and crit damage
at the far edge of W. A crit is taken as twice normal damage.

One press, at the right time (Lexer, 2026-09-26: mashing Square won every hit):

- Square only counts while an action plays (Lexer, 2026-09-28: outside an
  attack the code should not fire at all). 0050A790 starts an action's
  animation task when the scheduler dispatches its message 0x68, for party
  and enemy actions alike; the scheduler removes that message (00500D51)
  when the action is over. Outside that, a press does nothing and makes no
  sound. A press left over from the last action is cleared silently.
- One try per hit (Lexer, 2026-09-28). The first press arms the next hit,
  and every other press before that hit lands counts for nothing. A second
  press while armed is a fumble: the miss sound plays at once (once), and
  the hit counts as unpressed (Lexer, 2026-09-27: mashing with Squall was
  silent until the hit, then sounded two or three times). The try comes
  back when the hit lands.
- A press is judged when the hit lands, however early it was, so an early
  press in an attack always gets its miss sound. A press in an action that
  never hits (a cure, an item) is never judged and stays silent.
- A press after a hit lands counts for nothing on that hit: it arms the
  next one, so the hits of a multi-hit attack can each be timed.

Sounds: the crit sound for the best outcome (a crit, or a dodge), the hit
sound for a normal hit or a normal block, the miss sound for a press that
misses or lets the enemy crit. An unpressed hit is silent.

Against FF8_EN.exe SHA-256 064d466b...9570 (see codex/ff8/timed-hits.md):

- Presses: the battle input routine 004A84E0 stores this frame's newly
  pressed buttons at [01D6D490] + 0x12. The hook at 004A8554 records
  timeGetTime (import 00B69378) when bit 0x80 (Square) is newly pressed.
- Physical attacks (damage types 1 and the others routed through 00492B00):
  00492B00 decides an automatic hit (hit rate 255, or a sleeping or stopped
  target), 00492BA0 rolls the hit and 00492B30 rolls the crit, each by
  comparing a 0-255 threshold with the game's random byte (0048F020). The
  threshold is whatever the active formula made it. The hook replaces the
  random byte with the verdict: 0 to land, or a zeroed threshold to fail. An
  automatic hit is a 100% hit chance. A 0% enemy attack keeps its own miss.
- Types 34 and 36 go to 00492E10 instead, which rolls the same way with the
  threshold in EDI, the attacker x 0xD0 in ESI and the target x 0xD0 in EBP.
  Its automatic hit only rolls the crit (00492EA3), so an attack's miss there
  returns into the routine's own miss exit, 004930CB.
- Squall's gunblade (type 10, 0048F480) never rolls: its hit chance is 100%.
  His hit lands through 00485160 when his own trigger window closes; only
  that call, with the hit counter 01D28D90 set, is judged. A miss takes the
  handler's own no-damage exit with the miss mark (01D27ADE bit 4); a crit
  sets the crit flag 01D28E07, which the handler doubles at 0048F652, and
  the crit mark (bit 2). The crit threshold is the one 00492B30 uses:
  (attacker LUCK + the attack's crit bonus 01D2A23B) x 255 / 256.
- Continuous grading scales the hit's damage at 00491124, just before the
  damage cap, where ESI is the damage; the scale is worked out at the roll.
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
DEFAULT_CONTINUOUS = False
DEFAULT_SUCCESS_SOUND = 1   # the menu confirm sound (menu sounds 1 and 2)
DEFAULT_CRIT_SOUND = 9      # menu sound 3 in the table at 00B87D28
DEFAULT_FAILURE_SOUND = 16  # the menu denied buzz (menu sound 5)
MAX_SOUND = 2790            # audio.fmt holds 2791 entries; 0 is blank
EARLY_FACTOR = 3            # stored for old patches' layout; no longer read

INPUT_HOOK = 0x004A8554
INPUT_ORIGINAL = bytes.fromhex("66 8B 41 10 66 89 41 18")
INPUT_RESUME = 0x004A855C
BATTLE_INPUT = 0x01D6D490   # pointer; +0x12 newly pressed
SQUARE = 0x80  # FF8 function bits: L2 01 R2 02 L1 04 R1 08 Tri 10 O 20 X 40 Sq 80
HIT_HOOK = 0x00491124
HIT_ORIGINAL = bytes.fromhex("8A 0D 0E 8E D2 01")  # mov cl, [01D28E0E]
HIT_RESUME = 0x0049112A
ACTION_HOOK = 0x0050A790
ACTION_ORIGINAL = bytes.fromhex("56 8B 74 24 08")  # push esi; mov esi, [esp+8]
ACTION_RESUME = 0x0050A795
ACTION_END_HOOK = 0x00500D51
ACTION_END_ORIGINAL = bytes.fromhex("68 68 6D D9 01")  # push 01D96D68 (the scheduler queue)
ACTION_END_RESUME = 0x00500D56
ACTION_MESSAGE = 0x68
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
DATA = 0x027AC000
WINDOW = DATA + 0x00
EARLY = DATA + 0x04
CONTINUOUS = DATA + 0x08
SOUND_SUCCESS = DATA + 0x0C
SOUND_CRIT = DATA + 0x10
SOUND_FAILURE = DATA + 0x14
PRESS_TIME = DATA + 0x18
PRESSED = DATA + 0x1C
SCALE = DATA + 0x20         # continuous grading: the next damage x SCALE / 1000
SCALE_PENDING = DATA + 0x24
LAST_HIT = DATA + 0x28      # time the last judged hit landed
FUMBLED = DATA + 0x2C       # a second press arrived while armed
DEFENDING = DATA + 0x30     # a block's hit roll landed: its crit roll is judged
JUDGED = DATA + 0x34        # the judged press's lead over its hit, or -1
HIT_WINDOW = DATA + 0x38    # an attack's hit window, or a block's dodge band
FORCE_MISS = DATA + 0x3C    # an automatic hit that missed: fail the roll after it
ACTION_START = DATA + 0x40  # when the current action's animation started
ACTIVE = DATA + 0x44        # an action is playing: Square counts
DATA_SIZE = 0x48

ASSEMBLY = f"""
input:
    mov ax, word ptr [ecx + 0x10]
    mov word ptr [ecx + 0x18], ax
    test byte ptr [ecx + 0x12], {SQUARE:#x}
    jz input_done
    cmp dword ptr [{ACTIVE:#x}], 0
    je input_done
    pushad
    call dword ptr [{TIME_GET_TIME:#x}]
    cmp dword ptr [{PRESSED:#x}], 0
    je arm
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

action:
    pushad
    pushfd
    mov dword ptr [{PRESSED:#x}], 0
    mov dword ptr [{FUMBLED:#x}], 0
    mov dword ptr [{ACTIVE:#x}], 1
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{ACTION_START:#x}], eax
    popfd
    popad
    push esi
    mov esi, dword ptr [esp + 8]
    push {ACTION_RESUME:#x}
    ret

action_end:
    cmp word ptr [esi + 2], {ACTION_MESSAGE:#x}
    jne action_end_resume
    mov dword ptr [{ACTIVE:#x}], 0
action_end_resume:
    push 0x1d96d68
    push {ACTION_END_RESUME:#x}
    ret

take_press:
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{LAST_HIT:#x}], eax
    cmp dword ptr [{PRESSED:#x}], 0
    je take_none
    mov dword ptr [{PRESSED:#x}], 0
    sub eax, dword ptr [{PRESS_TIME:#x}]
    cmp dword ptr [{FUMBLED:#x}], 0
    jne take_none
    ret
take_none:
    mov eax, 0xffffffff
    ret

off_hit:
    push ebx
    mov ebx, dword ptr [esp + 8]
    cmp ebx, 255
    jbe off_hit_clamped
    mov ebx, 255
off_hit_clamped:
    mov dword ptr [{SCALE_PENDING:#x}], 0
    mov dword ptr [{DEFENDING:#x}], 0
    mov dword ptr [{JUDGED:#x}], 0xffffffff
    call take_press
    cmp eax, 0xffffffff
    je off_hit_miss
    mov ecx, eax
    mov eax, dword ptr [{WINDOW:#x}]
    mul ebx
    push ecx
    mov ecx, 255
    div ecx
    pop ecx
    test ebx, ebx
    jz off_hit_miss_sound
    cmp ecx, eax
    ja off_hit_miss_sound
    mov dword ptr [{HIT_WINDOW:#x}], eax
    mov dword ptr [{JUDGED:#x}], ecx
    mov eax, 1
    pop ebx
    ret
off_hit_miss_sound:
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
off_hit_miss:
    xor eax, eax
    pop ebx
    ret

off_crit:
    push ebx
    push esi
    mov ebx, dword ptr [esp + 0xc]
    cmp ebx, 255
    jbe off_crit_clamped
    mov ebx, 255
off_crit_clamped:
    mov esi, dword ptr [{JUDGED:#x}]
    cmp esi, 0xffffffff
    je off_crit_none
    mov dword ptr [{JUDGED:#x}], 0xffffffff
    mov eax, dword ptr [{HIT_WINDOW:#x}]
    mul ebx
    mov ecx, 255
    div ecx
    test ebx, ebx
    jz off_crit_plain
    cmp esi, eax
    ja off_crit_plain
    mov ecx, eax
    mov eax, 1000
    test ecx, ecx
    jz off_crit_scaled
    imul eax, esi, 500
    xor edx, edx
    div ecx
    neg eax
    add eax, 1000
off_crit_scaled:
    cmp dword ptr [{CONTINUOUS:#x}], 0
    je off_crit_graded
    mov dword ptr [{SCALE:#x}], eax
    mov dword ptr [{SCALE_PENDING:#x}], 1
off_crit_graded:
    push dword ptr [{SOUND_CRIT:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    mov eax, 1
    pop esi
    pop ebx
    ret
off_crit_plain:
    mov ecx, dword ptr [{HIT_WINDOW:#x}]
    sub ecx, eax
    mov eax, dword ptr [{HIT_WINDOW:#x}]
    sub eax, esi
    imul eax, eax, 1000
    test ecx, ecx
    jnz off_plain_divide
    mov eax, 1000
    jmp off_plain_scaled
off_plain_divide:
    xor edx, edx
    div ecx
off_plain_scaled:
    cmp dword ptr [{CONTINUOUS:#x}], 0
    je off_plain_graded
    mov dword ptr [{SCALE:#x}], eax
    mov dword ptr [{SCALE_PENDING:#x}], 1
off_plain_graded:
    push dword ptr [{SOUND_SUCCESS:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
off_crit_none:
    xor eax, eax
    pop esi
    pop ebx
    ret

def_hit:
    push ebx
    mov ebx, dword ptr [esp + 8]
    cmp ebx, 255
    jbe def_hit_clamped
    mov ebx, 255
def_hit_clamped:
    mov dword ptr [{SCALE_PENDING:#x}], 0
    mov dword ptr [{DEFENDING:#x}], 0
    test ebx, ebx
    jz def_hit_misses
    call take_press
    mov ecx, eax
    mov eax, 255
    sub eax, ebx
    mul dword ptr [{WINDOW:#x}]
    push ecx
    mov ecx, 255
    div ecx
    pop ecx
    mov dword ptr [{HIT_WINDOW:#x}], eax
    mov dword ptr [{JUDGED:#x}], ecx
    mov dword ptr [{DEFENDING:#x}], 1
    cmp ecx, 0xffffffff
    je def_hit_lands
    test eax, eax
    jz def_hit_lands
    cmp ecx, eax
    ja def_hit_lands
    mov dword ptr [{DEFENDING:#x}], 0
    push dword ptr [{SOUND_CRIT:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
def_hit_misses:
    xor eax, eax
    pop ebx
    ret
def_hit_lands:
    mov eax, 1
    pop ebx
    ret

def_crit:
    push ebx
    push esi
    push edi
    mov ebx, dword ptr [esp + 0x10]
    cmp ebx, 255
    jbe def_crit_clamped
    mov ebx, 255
def_crit_clamped:
    cmp dword ptr [{DEFENDING:#x}], 0
    je def_crit_game
    mov dword ptr [{DEFENDING:#x}], 0
    mov esi, dword ptr [{JUDGED:#x}]
    mov edi, dword ptr [{HIT_WINDOW:#x}]
    mov eax, 255
    sub eax, ebx
    mov ecx, dword ptr [{WINDOW:#x}]
    sub ecx, edi
    mul ecx
    mov ecx, 255
    div ecx
    cmp esi, 0xffffffff
    je def_crit_worst
    mov ecx, esi
    sub ecx, edi
    cmp ecx, eax
    ja def_crit_worst
    test eax, eax
    jz def_band_full
    imul ecx, ecx, 1000
    xchg eax, ecx
    xor edx, edx
    div ecx
    jmp def_band_scaled
def_band_full:
    mov eax, 1000
def_band_scaled:
    cmp dword ptr [{CONTINUOUS:#x}], 0
    je def_band_graded
    mov dword ptr [{SCALE:#x}], eax
    mov dword ptr [{SCALE_PENDING:#x}], 1
def_band_graded:
    push dword ptr [{SOUND_SUCCESS:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    xor eax, eax
    jmp def_crit_done
def_crit_worst:
    test ebx, ebx
    jz def_crit_plain_worst
    mov ecx, dword ptr [{WINDOW:#x}]
    sub ecx, edi
    sub ecx, eax
    cmp esi, 0xffffffff
    je def_crit_full
    cmp esi, dword ptr [{WINDOW:#x}]
    ja def_crit_full
    test ecx, ecx
    jz def_crit_full
    mov edx, esi
    sub edx, edi
    sub edx, eax
    imul eax, edx, 500
    xor edx, edx
    div ecx
    add eax, 500
    jmp def_crit_scaled
def_crit_full:
    mov eax, 1000
def_crit_scaled:
    cmp dword ptr [{CONTINUOUS:#x}], 0
    je def_crit_graded
    mov dword ptr [{SCALE:#x}], eax
    mov dword ptr [{SCALE_PENDING:#x}], 1
def_crit_graded:
    cmp esi, 0xffffffff
    je def_crit_quiet
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
def_crit_quiet:
    mov eax, 1
    jmp def_crit_done
def_crit_plain_worst:
    cmp esi, 0xffffffff
    je def_crit_quiet_plain
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
def_crit_quiet_plain:
    xor eax, eax
    jmp def_crit_done
def_crit_game:
    mov eax, 2
def_crit_done:
    pop edi
    pop esi
    pop ebx
    ret

auto:
    mov eax, dword ptr [esp + 4]
    mov ecx, dword ptr [esp + 8]
    cmp eax, {PARTY_SIZE}
    jb auto_party_attacks
    cmp ecx, {PARTY_SIZE}
    jae auto_hit
    push 255
    call def_hit
    add esp, 4
    ret
auto_party_attacks:
    cmp ecx, {PARTY_SIZE}
    jb auto_hit
    push 255
    call off_hit
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
    mov eax, dword ptr [esp + 0xc]
    mov ecx, dword ptr [esp + 0x10]
    cmp eax, {PARTY_SIZE}
    jb hit_roll_party
    cmp ecx, {PARTY_SIZE}
    jae real_random
    test esi, esi
    jz real_random
    push esi
    call def_hit
    add esp, 4
    jmp roll_verdict
hit_roll_party:
    cmp ecx, {PARTY_SIZE}
    jb real_random
    cmp dword ptr [{FORCE_MISS:#x}], 0
    je hit_roll_judge
    mov dword ptr [{FORCE_MISS:#x}], 0
    xor esi, esi
    ret
hit_roll_judge:
    push esi
    call off_hit
    add esp, 4
roll_verdict:
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
    mov eax, dword ptr [esp + 0xc]
    mov ecx, dword ptr [esp + 0x10]
    cmp eax, {PARTY_SIZE}
    jb crit_roll_party
    cmp ecx, {PARTY_SIZE}
    jae real_random
    push esi
    call def_crit
    add esp, 4
    cmp eax, 2
    je real_random
    jmp roll_verdict
crit_roll_party:
    cmp ecx, {PARTY_SIZE}
    jb real_random
    push esi
    call off_crit
    add esp, 4
    jmp roll_verdict

e10_hit_roll:
    cmp esi, {PARTY_OFFSET:#x}
    jb e10_hit_party
    cmp ebp, {PARTY_OFFSET:#x}
    jae real_random
    test edi, edi
    jz real_random
    push edi
    call def_hit
    add esp, 4
    jmp e10_verdict
e10_hit_party:
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push edi
    call off_hit
    add esp, 4
e10_verdict:
    test eax, eax
    jz e10_fails
    xor eax, eax
    ret
e10_fails:
    xor edi, edi
    ret

e10_crit_roll:
    cmp esi, {PARTY_OFFSET:#x}
    jb e10_crit_party
    cmp ebp, {PARTY_OFFSET:#x}
    jae real_random
    push edi
    call def_crit
    add esp, 4
    cmp eax, 2
    je real_random
    jmp e10_verdict
e10_crit_party:
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push edi
    call off_crit
    add esp, 4
    jmp e10_verdict

e10_auto_crit:
    cmp esi, {PARTY_OFFSET:#x}
    jb e10_auto_party
    cmp ebp, {PARTY_OFFSET:#x}
    jae real_random
    push 255
    call def_hit
    add esp, 4
    jmp e10_crit_roll
e10_auto_party:
    cmp ebp, {PARTY_OFFSET:#x}
    jb real_random
    push 255
    call off_hit
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
    call off_hit
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
    call off_crit
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
    cmp dword ptr [{SCALE_PENDING:#x}], 0
    je hit_done
    mov dword ptr [{SCALE_PENDING:#x}], 0
    test esi, esi
    jle hit_done
    mov eax, dword ptr [esp + 8]
    imul eax, dword ptr [{SCALE:#x}]
    xor edx, edx
    mov ecx, 1000
    div ecx
    mov dword ptr [esp + 8], eax
hit_done:
    popfd
    popad
    mov cl, byte ptr [0x1d28e0e]
    push {HIT_RESUME:#x}
    ret
"""

ENTRY_LABELS = ("hit", "action", "action_end", "auto", "hit_roll", "crit_roll", "gunblade",
                "e10_hit_roll", "e10_crit_roll", "e10_auto_crit")

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_timed_hits.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "66 8B 41 10 66 89 41 18 F6 41 12 80 74 56 83 3D"
    "44 C0 7A 02 00 74 4D 60 FF 15 78 93 B6 00 83 3D"
    "1C C0 7A 02 00 74 23 83 3D 2C C0 7A 02 00 75 33"
    "C7 05 2C C0 7A 02 01 00 00 00 FF 35 14 C0 7A 02"
    "E8 3B F9 CB FD 83 C4 04 EB 19 A3 18 C0 7A 02 C7"
    "05 1C C0 7A 02 01 00 00 00 C7 05 2C C0 7A 02 00"
    "00 00 00 61 68 5C 85 4A 00 C3 60 9C C7 05 1C C0"
    "7A 02 00 00 00 00 C7 05 2C C0 7A 02 00 00 00 00"
    "C7 05 44 C0 7A 02 01 00 00 00 FF 15 78 93 B6 00"
    "A3 40 C0 7A 02 9D 61 56 8B 74 24 08 68 95 A7 50"
    "00 C3 66 83 7E 02 68 75 0A C7 05 44 C0 7A 02 00"
    "00 00 00 68 68 6D D9 01 68 56 0D 50 00 C3 FF 15"
    "78 93 B6 00 A3 28 C0 7A 02 83 3D 1C C0 7A 02 00"
    "74 1A C7 05 1C C0 7A 02 00 00 00 00 2B 05 18 C0"
    "7A 02 83 3D 2C C0 7A 02 00 75 01 C3 B8 FF FF FF"
    "FF C3 53 8B 5C 24 08 81 FB FF 00 00 00 76 05 BB"
    "FF 00 00 00 C7 05 24 C0 7A 02 00 00 00 00 C7 05"
    "30 C0 7A 02 00 00 00 00 C7 05 34 C0 7A 02 FF FF"
    "FF FF E8 97 FF FF FF 83 F8 FF 74 3A 89 C1 A1 00"
    "C0 7A 02 F7 E3 51 B9 FF 00 00 00 F7 F1 59 85 DB"
    "74 16 39 C1 77 12 A3 38 C0 7A 02 89 0D 34 C0 7A"
    "02 B8 01 00 00 00 5B C3 FF 35 14 C0 7A 02 E8 1D"
    "F8 CB FD 83 C4 04 31 C0 5B C3 53 56 8B 5C 24 0C"
    "81 FB FF 00 00 00 76 05 BB FF 00 00 00 8B 35 34"
    "C0 7A 02 83 FE FF 0F 84 B4 00 00 00 C7 05 34 C0"
    "7A 02 FF FF FF FF A1 38 C0 7A 02 F7 E3 B9 FF 00"
    "00 00 F7 F1 85 DB 74 4E 39 C6 77 4A 89 C1 B8 E8"
    "03 00 00 85 C9 74 11 69 C6 F4 01 00 00 31 D2 F7"
    "F1 F7 D8 05 E8 03 00 00 83 3D 08 C0 7A 02 00 74"
    "0F A3 20 C0 7A 02 C7 05 24 C0 7A 02 01 00 00 00"
    "FF 35 10 C0 7A 02 E8 95 F7 CB FD 83 C4 04 B8 01"
    "00 00 00 5E 5B C3 8B 0D 38 C0 7A 02 29 C1 A1 38"
    "C0 7A 02 29 F0 69 C0 E8 03 00 00 85 C9 75 07 B8"
    "E8 03 00 00 EB 04 31 D2 F7 F1 83 3D 08 C0 7A 02"
    "00 74 0F A3 20 C0 7A 02 C7 05 24 C0 7A 02 01 00"
    "00 00 FF 35 0C C0 7A 02 E8 43 F7 CB FD 83 C4 04"
    "31 C0 5E 5B C3 53 8B 5C 24 08 81 FB FF 00 00 00"
    "76 05 BB FF 00 00 00 C7 05 24 C0 7A 02 00 00 00"
    "00 C7 05 30 C0 7A 02 00 00 00 00 85 DB 74 57 E8"
    "4A FE FF FF 89 C1 B8 FF 00 00 00 29 D8 F7 25 00"
    "C0 7A 02 51 B9 FF 00 00 00 F7 F1 59 A3 38 C0 7A"
    "02 89 0D 34 C0 7A 02 C7 05 30 C0 7A 02 01 00 00"
    "00 83 F9 FF 74 24 85 C0 74 20 39 C1 77 1C C7 05"
    "30 C0 7A 02 00 00 00 00 FF 35 10 C0 7A 02 E8 BD"
    "F6 CB FD 83 C4 04 31 C0 5B C3 B8 01 00 00 00 5B"
    "C3 53 56 57 8B 5C 24 10 81 FB FF 00 00 00 76 05"
    "BB FF 00 00 00 83 3D 30 C0 7A 02 00 0F 84 02 01"
    "00 00 C7 05 30 C0 7A 02 00 00 00 00 8B 35 34 C0"
    "7A 02 8B 3D 38 C0 7A 02 B8 FF 00 00 00 29 D8 8B"
    "0D 00 C0 7A 02 29 F9 F7 E1 B9 FF 00 00 00 F7 F1"
    "83 FE FF 74 4B 89 F1 29 F9 39 C1 77 43 85 C0 74"
    "0D 69 C9 E8 03 00 00 91 31 D2 F7 F1 EB 05 B8 E8"
    "03 00 00 83 3D 08 C0 7A 02 00 74 0F A3 20 C0 7A"
    "02 C7 05 24 C0 7A 02 01 00 00 00 FF 35 0C C0 7A"
    "02 E8 1A F6 CB FD 83 C4 04 31 C0 E9 89 00 00 00"
    "85 DB 74 69 8B 0D 00 C0 7A 02 29 F9 29 C1 83 FE"
    "FF 74 23 3B 35 00 C0 7A 02 77 1B 85 C9 74 17 89"
    "F2 29 FA 29 C2 69 C2 F4 01 00 00 31 D2 F7 F1 05"
    "F4 01 00 00 EB 05 B8 E8 03 00 00 83 3D 08 C0 7A"
    "02 00 74 0F A3 20 C0 7A 02 C7 05 24 C0 7A 02 01"
    "00 00 00 83 FE FF 74 0E FF 35 14 C0 7A 02 E8 AD"
    "F5 CB FD 83 C4 04 B8 01 00 00 00 EB 1C 83 FE FF"
    "74 0E FF 35 14 C0 7A 02 E8 93 F5 CB FD 83 C4 04"
    "31 C0 EB 05 B8 02 00 00 00 5F 5E 5B C3 8B 44 24"
    "04 8B 4C 24 08 83 F8 03 72 13 83 F9 03 73 2F 68"
    "FF 00 00 00 E8 2C FE FF FF 83 C4 04 C3 83 F9 03"
    "72 1C 68 FF 00 00 00 E8 C6 FC FF FF 83 C4 04 85"
    "C0 75 10 C7 05 3C C0 7A 02 01 00 00 00 C3 B8 01"
    "00 00 00 C3 8B 44 24 0C 8B 4C 24 10 83 F8 03 72"
    "14 83 F9 03 73 3D 85 F6 74 39 56 E8 E5 FD FF FF"
    "83 C4 04 EB 24 83 F9 03 72 29 83 3D 3C C0 7A 02"
    "00 74 0D C7 05 3C C0 7A 02 00 00 00 00 31 F6 C3"
    "56 E8 6C FC FF FF 83 C4 04 85 C0 74 03 31 C0 C3"
    "31 F6 C3 E9 88 32 CE FD 8B 44 24 0C 8B 4C 24 10"
    "83 F8 03 72 15 83 F9 03 73 E9 56 E8 21 FE FF FF"
    "83 C4 04 83 F8 02 74 DB EB CF 83 F9 03 72 D4 56"
    "E8 A5 FC FF FF 83 C4 04 EB BF 81 FE 70 02 00 00"
    "72 17 81 FD 70 02 00 00 73 B9 85 FF 74 B5 57 E8"
    "61 FD FF FF 83 C4 04 EB 11 81 FD 70 02 00 00 72"
    "A2 57 E8 FB FB FF FF 83 C4 04 85 C0 74 03 31 C0"
    "C3 31 FF C3 81 FE 70 02 00 00 72 20 81 FD 70 02"
    "00 00 0F 83 7B FF FF FF 57 E8 B3 FD FF FF 83 C4"
    "04 83 F8 02 0F 84 69 FF FF FF EB CE 81 FD 70 02"
    "00 00 0F 82 5B FF FF FF 57 E8 2C FC FF FF 83 C4"
    "04 EB B7 81 FE 70 02 00 00 72 1B 81 FD 70 02 00"
    "00 0F 83 3C FF FF FF 68 FF 00 00 00 E8 E4 FC FF"
    "FF 83 C4 04 EB 9E 81 FD 70 02 00 00 0F 82 21 FF"
    "FF FF 68 FF 00 00 00 E8 76 FB FF FF 83 C4 04 85"
    "C0 75 81 C7 04 24 CB 30 49 00 C3 60 9C 83 7C 24"
    "2C 03 73 5E 83 FD 03 72 59 66 83 3D 90 8D D2 01"
    "00 74 4F 68 FF 00 00 00 E8 45 FB FF FF 83 C4 04"
    "85 C0 74 4D 8B 44 24 2C 69 C0 D0 00 00 00 0F B6"
    "80 D2 7B D2 01 0F B6 0D 3B A2 D2 01 01 C8 69 C0"
    "FF 00 00 00 C1 E8 08 50 E8 8D FB FF FF 83 C4 04"
    "85 C0 74 0E C6 05 07 8E D2 01 01 80 0D DE 7A D2"
    "01 02 9D 61 53 31 DB 8D 44 95 00 68 37 F5 48 00"
    "C3 9D 61 80 0D DE 7A D2 01 04 68 22 F5 48 00 C3"
    "60 9C 83 3D 24 C0 7A 02 00 74 26 C7 05 24 C0 7A"
    "02 00 00 00 00 85 F6 7E 18 8B 44 24 08 0F AF 05"
    "20 C0 7A 02 31 D2 B9 E8 03 00 00 F7 F1 89 44 24"
    "08 9D 61 8A 0D 0E 8E D2 01 68 2A 11 49 00 C3"
)
ENTRIES = {
    "hit": 0x27abf10,
    "action": 0x27ab96a,
    "action_end": 0x27ab9a2,
    "auto": 0x27abcfd,
    "hit_roll": 0x27abd44,
    "crit_roll": 0x27abd98,
    "gunblade": 0x27abe8b,
    "e10_hit_roll": 0x27abdca,
    "e10_crit_roll": 0x27abe04,
    "e10_auto_crit": 0x27abe43,
}
HIT_ENTRY = ENTRIES.get("hit", 0)


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


def data_bytes(window_ms: int, success_sound: int, crit_sound: int, failure_sound: int,
               continuous: bool = False) -> bytes:
    values = (window_ms, window_ms * EARLY_FACTOR, int(continuous), success_sound, crit_sound,
              failure_sound, 0, 0, 1000, 0, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0, 0)
    return b"".join(value.to_bytes(4, "little") for value in values)


def _jump(site: int, target: int, length: int) -> bytes:
    rel = (target - (site + 5)).to_bytes(4, "little", signed=True)
    return b"\xE9" + rel + b"\x90" * (length - 5)


def _call(site: int, target: int) -> bytes:
    return b"\xE8" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def build_hext(enabled: bool, *, window_ms: int = DEFAULT_WINDOW_MS,
               success_sound: int = DEFAULT_SUCCESS_SOUND,
               crit_sound: int = DEFAULT_CRIT_SOUND,
               failure_sound: int = DEFAULT_FAILURE_SOUND,
               continuous: bool = DEFAULT_CONTINUOUS) -> str:
    """The patch with the chosen settings in its data, or nothing when off."""
    if not isinstance(enabled, bool):
        raise ValueError("Timed Hits must be true or false")
    if not isinstance(continuous, bool):
        raise ValueError("Timed Hits continuous grading must be true or false")
    window_ms = _bounded(window_ms, MIN_WINDOW_MS, MAX_WINDOW_MS, "Timed Hits input window")
    success_sound = _bounded(success_sound, 1, MAX_SOUND, "Timed Hits hit sound")
    crit_sound = _bounded(crit_sound, 1, MAX_SOUND, "Timed Hits crit sound")
    failure_sound = _bounded(failure_sound, 1, MAX_SOUND, "Timed Hits miss sound")
    if not enabled:
        return ""
    data = data_bytes(window_ms, success_sound, crit_sound, failure_sound, continuous)
    lines = [
        f"# Timed Hits and Blocks: Square within {window_ms} ms before a hit decides it by the "
        f"attack's hit and crit chances{', with continuous grading' if continuous else ''}.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{DATA:X}:{DATA_SIZE:X}",
        f"{DATA:X} = {data.hex(' ').upper()}",
        f"{INPUT_HOOK:X} = {_jump(INPUT_HOOK, CAVE, len(INPUT_ORIGINAL)).hex(' ').upper()}",
        f"{HIT_HOOK:X} = {_jump(HIT_HOOK, ENTRIES['hit'], len(HIT_ORIGINAL)).hex(' ').upper()}",
        f"{ACTION_HOOK:X} = {_jump(ACTION_HOOK, ENTRIES['action'], len(ACTION_ORIGINAL)).hex(' ').upper()}",
        f"{ACTION_END_HOOK:X} = {_jump(ACTION_END_HOOK, ENTRIES['action_end'], len(ACTION_END_ORIGINAL)).hex(' ').upper()}",
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
    "timedHitsSuccessSound": ("success_sound", DEFAULT_SUCCESS_SOUND, 1, MAX_SOUND, "Timed Hits hit sound"),
    "timedHitsCritSound": ("crit_sound", DEFAULT_CRIT_SOUND, 1, MAX_SOUND, "Timed Hits crit sound"),
    "timedHitsFailureSound": ("failure_sound", DEFAULT_FAILURE_SOUND, 1, MAX_SOUND, "Timed Hits miss sound"),
    "timedHitsContinuous": ("continuous", DEFAULT_CONTINUOUS, False, True, "Timed Hits continuous grading"),
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
    return [(INPUT_HOOK, INPUT_ORIGINAL), (HIT_HOOK, HIT_ORIGINAL),
            (ACTION_HOOK, ACTION_ORIGINAL), (ACTION_END_HOOK, ACTION_END_ORIGINAL),
            (AUTO_HOOK, AUTO_ORIGINAL), (GUNBLADE_HOOK, GUNBLADE_ORIGINAL),
            *((site, _call(site, RANDOM)) for site in (HIT_ROLL_CALL, CRIT_ROLL_CALL, E10_AUTO_CRIT_CALL,
                                                       E10_HIT_ROLL_CALL, E10_CRIT_ROLL_CALL)),
            *((site, original) for site, original, _ in TRIGGER_STORES)]
