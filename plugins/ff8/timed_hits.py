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

When (2026-09-28 logs): the game applies an ordinary attack's damage the
moment the swing starts, and shows it about 2 seconds later, when the hit
visibly connects. The press is judged at that visible contact. At the swing
start the rolls are forced to a normal hit, their thresholds are noted, and
the result is not applied yet (the call to 00494410 at 004911BC is held).
At contact, 00506690(record) plays the target's reaction from the hit record;
there the press is judged, the damage applied through the game's own
00494410 (so KO works as usual), and the record's first-effect fields (+1 to
+0xB) rewritten from the result block the way 0048EF80 copies them, so the
number shows the real result. The second effect (004911FD, record +0xC on)
was applied at the swing and stays as the game recorded it.

The press is heard the moment it is made (Lexer: "the sound should play the
moment you hit the button. every time"). That needs the contact time before
it happens. The swing's own length gives it: from the attacker's attack
sequence starting (0050BB9E, in the action task 0050BB00) to the visible
contact takes the same number of frames each time for one model and one
attack sequence (26.4 and 26.0 frames for one enemy's sequence 0D in the
2026-09-28 log). The patch learns that delay at each first contact and, on
the next swing of the same model and sequence, predicts the contact. A press
while a contact is predicted is judged against it at once: the sound plays
then and the verdict is kept for the contact. Without a prediction (the first
swing of each attack) the press is judged when the hit lands, as before.

One press, at the right time (Lexer, 2026-09-26: mashing Square won every hit):

- 0050A790 starts an action's animation task when the scheduler dispatches
  its message 0x68, for party and enemy actions alike; the scheduler removes
  that message (00500D51) when the action is over. A press left over from
  the last action is cleared silently when the next one starts.
- Square only counts while an action plays (Lexer: outside an attack it
  should not fire at all); with the verdict at contact, that is every press
  that can matter.
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
DEFER_CALL = 0x004911BC       # call 00494410: apply one hit's result
APPLY = 0x00494410
CONTACT_HOOK = 0x00506690     # (record): play a hit's reaction and number
CONTACT_ORIGINAL = bytes.fromhex("53 56 8B 74 24 0C")  # push ebx; push esi; mov esi, [esp+0xc]
CONTACT_RESUME = 0x00506696
RECORDS = 0x01D28344          # hit records, 0x18 bytes each
RECORD_SIZE = 0x18
RECORD_COUNT = 0x01D280C1     # the next record's index
RESULT_BLOCK = 0x01D27AD8     # the hit's result, which 0048EF80 copies into its record
RESULT_SIZE = 0x28
SHOWN_DAMAGE = 0x01D27AE4     # record +6
SWING_CALL = 0x0050BB9E      # call 00505C00(attacker model, attack sequence)
START_SEQUENCE = 0x00505C00
MODELS = 0x01D972C0          # battle models, 0x9C bytes each
MODEL_SIZE = 0x9C
LEARNED_MODELS = 8
LEARNED_SEQUENCES = 32
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
DATA = 0x027AC800
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
THR_HIT = DATA + 0x48       # the hit threshold the roll had (0-255)
THR_CRIT = DATA + 0x4C      # the crit threshold the roll had
THR_VALID = DATA + 0x50     # a timed roll ran: hold the next result
OVERRIDE = DATA + 0x54      # a press judged ahead: its lead over the predicted contact, or -1
SWING_TIME = DATA + 0x58    # when the attacker's attack sequence started
SWING_KEY = DATA + 0x5C     # model x 32 + sequence, or -1
FIRST_PENDING = DATA + 0x60 # the action's first contact has not come yet
PREDICTED = DATA + 0x64     # the predicted time of that contact, or 0
SLOTS = DATA + 0x80         # held results, one per hit record
SLOT_COUNT = 16
SLOT_SIZE = 0x40            # +0 held, +1 block, +2 hit, +3 crit, +4 target, +8 attacker,
                            # +0xC damage, +0x10 the result block, +0x38 verdict
                            # (0 none, 1 miss, 2 hit, 3 crit), +0x3C damage scale / 1000
LEARNED = SLOTS + SLOT_COUNT * SLOT_SIZE  # contact delay (ms) per model and sequence
DATA_SIZE = LEARNED - DATA + LEARNED_MODELS * LEARNED_SEQUENCES * 4

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
    cmp dword ptr [{PREDICTED:#x}], 0
    je input_popped
    mov edx, dword ptr [{PREDICTED:#x}]
    sub edx, eax
    js input_popped
    mov ebx, {SLOTS:#x}
    mov ecx, {SLOT_COUNT}
input_find:
    cmp byte ptr [ebx], 0
    je input_next
    cmp byte ptr [ebx + 0x38], 0
    je input_found
input_next:
    add ebx, {SLOT_SIZE}
    dec ecx
    jnz input_find
    jmp input_popped
input_found:
    mov dword ptr [{OVERRIDE:#x}], edx
    call judge_slot
    mov dword ptr [{OVERRIDE:#x}], 0xffffffff
    mov dword ptr [{PRESSED:#x}], 1
    mov dword ptr [{FUMBLED:#x}], 1
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
    mov dword ptr [{THR_VALID:#x}], 0
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
    mov dword ptr [{PREDICTED:#x}], 0
    mov dword ptr [{FIRST_PENDING:#x}], 0
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
    cmp dword ptr [{OVERRIDE:#x}], 0xffffffff
    je take_measured
    mov eax, dword ptr [{OVERRIDE:#x}]
take_measured:
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

pair:
    cmp eax, 8
    jae pair_no
    cmp ecx, 8
    jae pair_no
    cmp eax, {PARTY_SIZE}
    jb pair_party
    cmp ecx, {PARTY_SIZE}
    jae pair_no
    mov eax, 1
    ret
pair_party:
    cmp ecx, {PARTY_SIZE}
    jb pair_no
    mov eax, 1
    ret
pair_no:
    xor eax, eax
    ret

note_full_hit:
    mov dword ptr [{THR_HIT:#x}], 255
    mov dword ptr [{THR_CRIT:#x}], 0
    mov dword ptr [{THR_VALID:#x}], 1
    ret

auto:
    mov eax, dword ptr [esp + 4]
    mov ecx, dword ptr [esp + 8]
    call pair
    test eax, eax
    jz auto_hit
    call note_full_hit
auto_hit:
    mov eax, 1
    ret

hit_roll:
    mov eax, dword ptr [esp + 0xc]
    mov ecx, dword ptr [esp + 0x10]
    call pair
    test eax, eax
    jz real_random
    test esi, esi
    jz real_random
    mov eax, esi
    cmp eax, 255
    jbe hit_roll_noted
    mov eax, 255
hit_roll_noted:
    mov dword ptr [{THR_HIT:#x}], eax
    mov dword ptr [{THR_CRIT:#x}], 0
    mov dword ptr [{THR_VALID:#x}], 1
    xor eax, eax
    ret
real_random:
    jmp {RANDOM:#x}

crit_roll:
    mov eax, dword ptr [esp + 0xc]
    mov ecx, dword ptr [esp + 0x10]
    call pair
    test eax, eax
    jz real_random
    mov eax, esi
    cmp eax, 255
    jbe crit_roll_noted
    mov eax, 255
crit_roll_noted:
    mov dword ptr [{THR_CRIT:#x}], eax
    xor esi, esi
    ret

offsets:
    mov eax, esi
    xor edx, edx
    mov ecx, 0xd0
    div ecx
    push eax
    mov eax, ebp
    xor edx, edx
    div ecx
    mov ecx, eax
    pop eax
    jmp pair

e10_hit_roll:
    call offsets
    test eax, eax
    jz real_random
    test edi, edi
    jz real_random
    mov eax, edi
    cmp eax, 255
    jbe e10_hit_noted
    mov eax, 255
e10_hit_noted:
    mov dword ptr [{THR_HIT:#x}], eax
    mov dword ptr [{THR_CRIT:#x}], 0
    mov dword ptr [{THR_VALID:#x}], 1
    xor eax, eax
    ret

e10_crit_roll:
    call offsets
    test eax, eax
    jz real_random
    mov eax, edi
    cmp eax, 255
    jbe e10_crit_noted
    mov eax, 255
e10_crit_noted:
    mov dword ptr [{THR_CRIT:#x}], eax
    xor edi, edi
    ret

e10_auto_crit:
    call offsets
    test eax, eax
    jz real_random
    call note_full_hit
    jmp e10_crit_roll

gunblade:
    pushad
    pushfd
    cmp dword ptr [esp + 0x2c], {PARTY_SIZE}
    jae gunblade_resume
    cmp ebp, {PARTY_SIZE}
    jb gunblade_resume
    cmp word ptr [{HIT_COUNTER:#x}], 0
    je gunblade_resume
    call note_full_hit
    mov eax, dword ptr [esp + 0x2c]
    imul eax, eax, 0xd0
    movzx eax, byte ptr [eax + {PARTICIPANTS + LUCK:#x}]
    movzx ecx, byte ptr [{CRIT_BONUS:#x}]
    add eax, ecx
    imul eax, eax, 255
    shr eax, 8
    mov dword ptr [{THR_CRIT:#x}], eax
gunblade_resume:
    popfd
    popad
    push ebx
    xor ebx, ebx
    lea eax, [ebp + edx*4]
    push {GUNBLADE_RESUME:#x}
    ret

judge_slot:
    movzx eax, byte ptr [ebx + 2]
    cmp byte ptr [ebx + 1], 0
    jne judge_block
    push eax
    call off_hit
    add esp, 4
    test eax, eax
    jz judge_miss
    movzx eax, byte ptr [ebx + 3]
    push eax
    call off_crit
    add esp, 4
    jmp judge_outcome
judge_block:
    push eax
    call def_hit
    add esp, 4
    test eax, eax
    jz judge_miss
    movzx eax, byte ptr [ebx + 3]
    push eax
    call def_crit
    add esp, 4
    cmp eax, 2
    jne judge_outcome
    xor eax, eax
judge_outcome:
    add eax, 2
    mov byte ptr [ebx + 0x38], al
    mov dword ptr [ebx + 0x3c], 1000
    cmp dword ptr [{SCALE_PENDING:#x}], 0
    je judge_done
    mov dword ptr [{SCALE_PENDING:#x}], 0
    mov eax, dword ptr [{SCALE:#x}]
    mov dword ptr [ebx + 0x3c], eax
    ret
judge_miss:
    mov byte ptr [ebx + 0x38], 1
    mov dword ptr [ebx + 0x3c], 1000
judge_done:
    ret

swing:
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{SWING_TIME:#x}], eax
    mov dword ptr [{PREDICTED:#x}], 0
    mov dword ptr [{FIRST_PENDING:#x}], 1
    mov dword ptr [{SWING_KEY:#x}], 0xffffffff
    mov eax, dword ptr [esp + 4]
    sub eax, {MODELS:#x}
    jb swing_done
    xor edx, edx
    mov ecx, {MODEL_SIZE}
    div ecx
    test edx, edx
    jnz swing_done
    cmp eax, {LEARNED_MODELS}
    jae swing_done
    mov ecx, dword ptr [esp + 8]
    and ecx, 0xff
    cmp ecx, {LEARNED_SEQUENCES}
    jae swing_done
    shl eax, 5
    add eax, ecx
    mov dword ptr [{SWING_KEY:#x}], eax
    mov edx, dword ptr [eax*4 + {LEARNED:#x}]
    test edx, edx
    jz swing_done
    add edx, dword ptr [{SWING_TIME:#x}]
    mov dword ptr [{PREDICTED:#x}], edx
swing_done:
    jmp {START_SEQUENCE:#x}

defer:
    cmp dword ptr [{THR_VALID:#x}], 0
    je apply_now
    mov dword ptr [{THR_VALID:#x}], 0
    mov eax, dword ptr [esp + 0x14]
    mov ecx, dword ptr [esp + 4]
    call pair
    test eax, eax
    jz apply_now
    movzx eax, byte ptr [{RECORD_COUNT:#x}]
    cmp eax, {SLOT_COUNT}
    jae apply_now
    test eax, eax
    jnz defer_slot
    mov ecx, {SLOTS:#x}
defer_clear:
    mov byte ptr [ecx], 0
    mov byte ptr [ecx + 0x38], 0
    add ecx, {SLOT_SIZE}
    cmp ecx, {SLOTS + SLOT_COUNT * SLOT_SIZE:#x}
    jb defer_clear
defer_slot:
    shl eax, 6
    add eax, {SLOTS:#x}
    push esi
    push edi
    mov edi, eax
    mov byte ptr [edi], 1
    mov byte ptr [edi + 0x38], 0
    mov ecx, dword ptr [esp + 0x1c]
    xor edx, edx
    cmp ecx, {PARTY_SIZE}
    setae dl
    mov byte ptr [edi + 1], dl
    mov ecx, dword ptr [{THR_HIT:#x}]
    mov byte ptr [edi + 2], cl
    mov ecx, dword ptr [{THR_CRIT:#x}]
    mov byte ptr [edi + 3], cl
    mov ecx, dword ptr [esp + 0xc]
    mov dword ptr [edi + 4], ecx
    mov ecx, dword ptr [esp + 0x1c]
    mov dword ptr [edi + 8], ecx
    mov ecx, dword ptr [esp + 0x10]
    mov dword ptr [edi + 0xc], ecx
    add edi, 0x10
    mov esi, {RESULT_BLOCK:#x}
    mov ecx, {RESULT_SIZE // 4}
defer_copy:
    mov edx, dword ptr [esi]
    mov dword ptr [edi], edx
    add esi, 4
    add edi, 4
    dec ecx
    jnz defer_copy
    pop edi
    pop esi
    ret
apply_now:
    jmp {APPLY:#x}

contact:
    pushad
    pushfd
    mov eax, dword ptr [esp + 0x28]
    cmp eax, {RECORDS:#x}
    jb contact_done
    sub eax, {RECORDS:#x}
    xor edx, edx
    mov ecx, {RECORD_SIZE}
    div ecx
    test edx, edx
    jnz contact_done
    cmp eax, {SLOT_COUNT}
    jae contact_done
    mov ebx, eax
    shl ebx, 6
    add ebx, {SLOTS:#x}
    cmp byte ptr [ebx], 0
    je contact_done
    mov byte ptr [ebx], 0
    lea esi, [ebx + 0x10]
    mov edi, {RESULT_BLOCK:#x}
    mov ecx, {RESULT_SIZE // 4}
contact_copy:
    mov edx, dword ptr [esi]
    mov dword ptr [edi], edx
    add esi, 4
    add edi, 4
    dec ecx
    jnz contact_copy
    cmp byte ptr [ebx + 0x38], 0
    je contact_judge
    mov dword ptr [{PRESSED:#x}], 0
    mov dword ptr [{FUMBLED:#x}], 0
    jmp contact_verdict
contact_judge:
    call judge_slot
contact_verdict:
    movzx eax, byte ptr [ebx + 0x38]
    mov byte ptr [ebx + 0x38], 0
    cmp eax, 1
    je contact_miss
    sub eax, 2
contact_outcome:
    mov ebp, dword ptr [ebx + 0xc]
    mov edi, 9999
    cmp ebp, edi
    jbe contact_limit
    mov edi, 60000
contact_limit:
    test eax, eax
    jz contact_graded
    add ebp, ebp
    cmp ebp, edi
    jbe contact_crit_capped
    mov ebp, edi
contact_crit_capped:
    or byte ptr [{HIT_MARKS:#x}], 2
contact_graded:
    cmp dword ptr [ebx + 0x3c], 1000
    je contact_apply
    mov eax, ebp
    imul eax, dword ptr [ebx + 0x3c]
    xor edx, edx
    mov ecx, 1000
    div ecx
    mov ebp, eax
contact_apply:
    mov word ptr [{SHOWN_DAMAGE:#x}], bp
    push 0
    push 0x1d27ae8
    push 0x1d27af6
    push 0x1d27adc
    push dword ptr [ebx + 8]
    push 0x1d27add
    push 0x1d27ade
    push ebp
    push dword ptr [ebx + 4]
    call {APPLY:#x}
    add esp, 0x24
    jmp contact_record
contact_miss:
    or byte ptr [{HIT_MARKS:#x}], 4
    mov word ptr [{SHOWN_DAMAGE:#x}], 0
contact_record:
    mov edi, dword ptr [esp + 0x28]
    mov al, byte ptr [0x1d27adc]
    mov byte ptr [edi + 1], al
    mov al, byte ptr [0x1d27add]
    mov byte ptr [edi + 2], al
    mov al, byte ptr [0x1d27ade]
    mov byte ptr [edi + 3], al
    mov ax, word ptr [0x1d27af6]
    mov word ptr [edi + 4], ax
    mov ax, word ptr [0x1d27ae4]
    mov word ptr [edi + 6], ax
    mov eax, dword ptr [0x1d27ae8]
    mov dword ptr [edi + 8], eax
    cmp dword ptr [{FIRST_PENDING:#x}], 0
    je contact_done
    mov dword ptr [{FIRST_PENDING:#x}], 0
    mov dword ptr [{PREDICTED:#x}], 0
    mov ecx, dword ptr [{SWING_KEY:#x}]
    cmp ecx, 0xffffffff
    je contact_done
    call dword ptr [{TIME_GET_TIME:#x}]
    sub eax, dword ptr [{SWING_TIME:#x}]
    mov ecx, dword ptr [{SWING_KEY:#x}]
    mov dword ptr [ecx*4 + {LEARNED:#x}], eax
contact_done:
    popfd
    popad
    push ebx
    push esi
    mov esi, dword ptr [esp + 0xc]
    push {CONTACT_RESUME:#x}
    ret
"""

ENTRY_LABELS = ("action", "action_end", "auto", "hit_roll", "crit_roll", "gunblade",
                "e10_hit_roll", "e10_crit_roll", "e10_auto_crit", "defer", "contact", "swing")


# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_timed_hits.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "66 8B 41 10 66 89 41 18 F6 41 12 80 0F 84 B7 00"
    "00 00 83 3D 44 C8 7A 02 00 0F 84 AA 00 00 00 60"
    "FF 15 78 93 B6 00 83 3D 1C C8 7A 02 00 74 27 83"
    "3D 2C C8 7A 02 00 0F 85 8C 00 00 00 C7 05 2C C8"
    "7A 02 01 00 00 00 FF 35 14 C8 7A 02 E8 2F F9 CB"
    "FD 83 C4 04 EB 72 A3 18 C8 7A 02 C7 05 1C C8 7A"
    "02 01 00 00 00 C7 05 2C C8 7A 02 00 00 00 00 83"
    "3D 64 C8 7A 02 00 74 50 8B 15 64 C8 7A 02 29 C2"
    "78 46 BB 80 C8 7A 02 B9 10 00 00 00 80 3B 00 74"
    "06 80 7B 38 00 74 08 83 C3 40 49 75 EF EB 29 89"
    "15 54 C8 7A 02 E8 8E 05 00 00 C7 05 54 C8 7A 02"
    "FF FF FF FF C7 05 1C C8 7A 02 01 00 00 00 C7 05"
    "2C C8 7A 02 01 00 00 00 61 68 5C 85 4A 00 C3 60"
    "9C C7 05 1C C8 7A 02 00 00 00 00 C7 05 2C C8 7A"
    "02 00 00 00 00 C7 05 44 C8 7A 02 01 00 00 00 C7"
    "05 50 C8 7A 02 00 00 00 00 FF 15 78 93 B6 00 A3"
    "40 C8 7A 02 9D 61 56 8B 74 24 08 68 95 A7 50 00"
    "C3 66 83 7E 02 68 75 1E C7 05 44 C8 7A 02 00 00"
    "00 00 C7 05 64 C8 7A 02 00 00 00 00 C7 05 60 C8"
    "7A 02 00 00 00 00 68 68 6D D9 01 68 56 0D 50 00"
    "C3 FF 15 78 93 B6 00 A3 28 C8 7A 02 83 3D 1C C8"
    "7A 02 00 74 28 C7 05 1C C8 7A 02 00 00 00 00 2B"
    "05 18 C8 7A 02 83 3D 54 C8 7A 02 FF 74 05 A1 54"
    "C8 7A 02 83 3D 2C C8 7A 02 00 75 01 C3 B8 FF FF"
    "FF FF C3 53 8B 5C 24 08 81 FB FF 00 00 00 76 05"
    "BB FF 00 00 00 C7 05 24 C8 7A 02 00 00 00 00 C7"
    "05 30 C8 7A 02 00 00 00 00 C7 05 34 C8 7A 02 FF"
    "FF FF FF E8 89 FF FF FF 83 F8 FF 74 3A 89 C1 A1"
    "00 C8 7A 02 F7 E3 51 B9 FF 00 00 00 F7 F1 59 85"
    "DB 74 16 39 C1 77 12 A3 38 C8 7A 02 89 0D 34 C8"
    "7A 02 B8 01 00 00 00 5B C3 FF 35 14 C8 7A 02 E8"
    "8C F7 CB FD 83 C4 04 31 C0 5B C3 53 56 8B 5C 24"
    "0C 81 FB FF 00 00 00 76 05 BB FF 00 00 00 8B 35"
    "34 C8 7A 02 83 FE FF 0F 84 B4 00 00 00 C7 05 34"
    "C8 7A 02 FF FF FF FF A1 38 C8 7A 02 F7 E3 B9 FF"
    "00 00 00 F7 F1 85 DB 74 4E 39 C6 77 4A 89 C1 B8"
    "E8 03 00 00 85 C9 74 11 69 C6 F4 01 00 00 31 D2"
    "F7 F1 F7 D8 05 E8 03 00 00 83 3D 08 C8 7A 02 00"
    "74 0F A3 20 C8 7A 02 C7 05 24 C8 7A 02 01 00 00"
    "00 FF 35 10 C8 7A 02 E8 04 F7 CB FD 83 C4 04 B8"
    "01 00 00 00 5E 5B C3 8B 0D 38 C8 7A 02 29 C1 A1"
    "38 C8 7A 02 29 F0 69 C0 E8 03 00 00 85 C9 75 07"
    "B8 E8 03 00 00 EB 04 31 D2 F7 F1 83 3D 08 C8 7A"
    "02 00 74 0F A3 20 C8 7A 02 C7 05 24 C8 7A 02 01"
    "00 00 00 FF 35 0C C8 7A 02 E8 B2 F6 CB FD 83 C4"
    "04 31 C0 5E 5B C3 53 8B 5C 24 08 81 FB FF 00 00"
    "00 76 05 BB FF 00 00 00 C7 05 24 C8 7A 02 00 00"
    "00 00 C7 05 30 C8 7A 02 00 00 00 00 85 DB 74 57"
    "E8 3C FE FF FF 89 C1 B8 FF 00 00 00 29 D8 F7 25"
    "00 C8 7A 02 51 B9 FF 00 00 00 F7 F1 59 A3 38 C8"
    "7A 02 89 0D 34 C8 7A 02 C7 05 30 C8 7A 02 01 00"
    "00 00 83 F9 FF 74 24 85 C0 74 20 39 C1 77 1C C7"
    "05 30 C8 7A 02 00 00 00 00 FF 35 10 C8 7A 02 E8"
    "2C F6 CB FD 83 C4 04 31 C0 5B C3 B8 01 00 00 00"
    "5B C3 53 56 57 8B 5C 24 10 81 FB FF 00 00 00 76"
    "05 BB FF 00 00 00 83 3D 30 C8 7A 02 00 0F 84 02"
    "01 00 00 C7 05 30 C8 7A 02 00 00 00 00 8B 35 34"
    "C8 7A 02 8B 3D 38 C8 7A 02 B8 FF 00 00 00 29 D8"
    "8B 0D 00 C8 7A 02 29 F9 F7 E1 B9 FF 00 00 00 F7"
    "F1 83 FE FF 74 4B 89 F1 29 F9 39 C1 77 43 85 C0"
    "74 0D 69 C9 E8 03 00 00 91 31 D2 F7 F1 EB 05 B8"
    "E8 03 00 00 83 3D 08 C8 7A 02 00 74 0F A3 20 C8"
    "7A 02 C7 05 24 C8 7A 02 01 00 00 00 FF 35 0C C8"
    "7A 02 E8 89 F5 CB FD 83 C4 04 31 C0 E9 89 00 00"
    "00 85 DB 74 69 8B 0D 00 C8 7A 02 29 F9 29 C1 83"
    "FE FF 74 23 3B 35 00 C8 7A 02 77 1B 85 C9 74 17"
    "89 F2 29 FA 29 C2 69 C2 F4 01 00 00 31 D2 F7 F1"
    "05 F4 01 00 00 EB 05 B8 E8 03 00 00 83 3D 08 C8"
    "7A 02 00 74 0F A3 20 C8 7A 02 C7 05 24 C8 7A 02"
    "01 00 00 00 83 FE FF 74 0E FF 35 14 C8 7A 02 E8"
    "1C F5 CB FD 83 C4 04 B8 01 00 00 00 EB 1C 83 FE"
    "FF 74 0E FF 35 14 C8 7A 02 E8 02 F5 CB FD 83 C4"
    "04 31 C0 EB 05 B8 02 00 00 00 5F 5E 5B C3 83 F8"
    "08 73 20 83 F9 08 73 1B 83 F8 03 72 0B 83 F9 03"
    "73 11 B8 01 00 00 00 C3 83 F9 03 72 06 B8 01 00"
    "00 00 C3 31 C0 C3 C7 05 48 C8 7A 02 FF 00 00 00"
    "C7 05 4C C8 7A 02 00 00 00 00 C7 05 50 C8 7A 02"
    "01 00 00 00 C3 8B 44 24 04 8B 4C 24 08 E8 AC FF"
    "FF FF 85 C0 74 05 E8 CB FF FF FF B8 01 00 00 00"
    "C3 8B 44 24 0C 8B 4C 24 10 E8 90 FF FF FF 85 C0"
    "74 2E 85 F6 74 2A 89 F0 3D FF 00 00 00 76 05 B8"
    "FF 00 00 00 A3 48 C8 7A 02 C7 05 4C C8 7A 02 00"
    "00 00 00 C7 05 50 C8 7A 02 01 00 00 00 31 C0 C3"
    "E9 EB 31 CE FD 8B 44 24 0C 8B 4C 24 10 E8 4C FF"
    "FF FF 85 C0 74 EA 89 F0 3D FF 00 00 00 76 05 B8"
    "FF 00 00 00 A3 4C C8 7A 02 31 F6 C3 89 F0 31 D2"
    "B9 D0 00 00 00 F7 F1 50 89 E8 31 D2 F7 F1 89 C1"
    "58 E9 18 FF FF FF E8 E1 FF FF FF 85 C0 74 B1 85"
    "FF 74 AD 89 F8 3D FF 00 00 00 76 05 B8 FF 00 00"
    "00 A3 48 C8 7A 02 C7 05 4C C8 7A 02 00 00 00 00"
    "C7 05 50 C8 7A 02 01 00 00 00 31 C0 C3 E8 AA FF"
    "FF FF 85 C0 0F 84 76 FF FF FF 89 F8 3D FF 00 00"
    "00 76 05 B8 FF 00 00 00 A3 4C C8 7A 02 31 FF C3"
    "E8 87 FF FF FF 85 C0 0F 84 53 FF FF FF E8 D4 FE"
    "FF FF EB C9 60 9C 83 7C 24 2C 03 73 3C 83 FD 03"
    "72 37 66 83 3D 90 8D D2 01 00 74 2D E8 B5 FE FF"
    "FF 8B 44 24 2C 69 C0 D0 00 00 00 0F B6 80 D2 7B"
    "D2 01 0F B6 0D 3B A2 D2 01 01 C8 69 C0 FF 00 00"
    "00 C1 E8 08 A3 4C C8 7A 02 9D 61 53 31 DB 8D 44"
    "95 00 68 37 F5 48 00 C3 0F B6 43 02 80 7B 01 00"
    "75 1C 50 E8 3B FB FF FF 83 C4 04 85 C0 74 59 0F"
    "B6 43 03 50 E8 A2 FB FF FF 83 C4 04 EB 21 50 E8"
    "72 FC FF FF 83 C4 04 85 C0 74 3D 0F B6 43 03 50"
    "E8 ED FC FF FF 83 C4 04 83 F8 02 75 02 31 C0 83"
    "C0 02 88 43 38 C7 43 3C E8 03 00 00 83 3D 24 C8"
    "7A 02 00 74 1E C7 05 24 C8 7A 02 00 00 00 00 A1"
    "20 C8 7A 02 89 43 3C C3 C6 43 38 01 C7 43 3C E8"
    "03 00 00 C3 FF 15 78 93 B6 00 A3 58 C8 7A 02 C7"
    "05 64 C8 7A 02 00 00 00 00 C7 05 60 C8 7A 02 01"
    "00 00 00 C7 05 5C C8 7A 02 FF FF FF FF 8B 44 24"
    "04 2D C0 72 D9 01 72 42 31 D2 B9 9C 00 00 00 F7"
    "F1 85 D2 75 35 83 F8 08 73 30 8B 4C 24 08 81 E1"
    "FF 00 00 00 83 F9 20 73 21 C1 E0 05 01 C8 A3 5C"
    "C8 7A 02 8B 14 85 80 CC 7A 02 85 D2 74 0C 03 15"
    "58 C8 7A 02 89 15 64 C8 7A 02 E9 D1 9B D5 FD 83"
    "3D 50 C8 7A 02 00 0F 84 B0 00 00 00 C7 05 50 C8"
    "7A 02 00 00 00 00 8B 44 24 14 8B 4C 24 04 E8 3B"
    "FD FF FF 85 C0 0F 84 91 00 00 00 0F B6 05 C1 80"
    "D2 01 83 F8 10 0F 83 81 00 00 00 85 C0 75 17 B9"
    "80 C8 7A 02 C6 01 00 C6 41 38 00 83 C1 40 81 F9"
    "80 CC 7A 02 72 EE C1 E0 06 05 80 C8 7A 02 56 57"
    "89 C7 C6 07 01 C6 47 38 00 8B 4C 24 1C 31 D2 83"
    "F9 03 0F 93 C2 88 57 01 8B 0D 48 C8 7A 02 88 4F"
    "02 8B 0D 4C C8 7A 02 88 4F 03 8B 4C 24 0C 89 4F"
    "04 8B 4C 24 1C 89 4F 08 8B 4C 24 10 89 4F 0C 83"
    "C7 10 BE D8 7A D2 01 B9 0A 00 00 00 8B 16 89 17"
    "83 C6 04 83 C7 04 49 75 F3 5F 5E C3 E9 1F 83 CE"
    "FD 60 9C 8B 44 24 28 3D 44 83 D2 01 0F 82 7B 01"
    "00 00 2D 44 83 D2 01 31 D2 B9 18 00 00 00 F7 F1"
    "85 D2 0F 85 65 01 00 00 83 F8 10 0F 83 5C 01 00"
    "00 89 C3 C1 E3 06 81 C3 80 C8 7A 02 80 3B 00 0F"
    "84 48 01 00 00 C6 03 00 8D 73 10 BF D8 7A D2 01"
    "B9 0A 00 00 00 8B 16 89 17 83 C6 04 83 C7 04 49"
    "75 F3 80 7B 38 00 74 16 C7 05 1C C8 7A 02 00 00"
    "00 00 C7 05 2C C8 7A 02 00 00 00 00 EB 05 E8 C5"
    "FD FF FF 0F B6 43 38 C6 43 38 00 83 F8 01 74 74"
    "83 E8 02 8B 6B 0C BF 0F 27 00 00 39 FD 76 05 BF"
    "60 EA 00 00 85 C0 74 0F 01 ED 39 FD 76 02 89 FD"
    "80 0D DE 7A D2 01 02 81 7B 3C E8 03 00 00 74 11"
    "89 E8 0F AF 43 3C 31 D2 B9 E8 03 00 00 F7 F1 89"
    "C5 66 89 2D E4 7A D2 01 6A 00 68 E8 7A D2 01 68"
    "F6 7A D2 01 68 DC 7A D2 01 FF 73 08 68 DD 7A D2"
    "01 68 DE 7A D2 01 55 FF 73 04 E8 21 82 CE FD 83"
    "C4 24 EB 10 80 0D DE 7A D2 01 04 66 C7 05 E4 7A"
    "D2 01 00 00 8B 7C 24 28 A0 DC 7A D2 01 88 47 01"
    "A0 DD 7A D2 01 88 47 02 A0 DE 7A D2 01 88 47 03"
    "66 A1 F6 7A D2 01 66 89 47 04 66 A1 E4 7A D2 01"
    "66 89 47 06 A1 E8 7A D2 01 89 47 08 83 3D 60 C8"
    "7A 02 00 74 38 C7 05 60 C8 7A 02 00 00 00 00 C7"
    "05 64 C8 7A 02 00 00 00 00 8B 0D 5C C8 7A 02 83"
    "F9 FF 74 19 FF 15 78 93 B6 00 2B 05 58 C8 7A 02"
    "8B 0D 5C C8 7A 02 89 04 8D 80 CC 7A 02 9D 61 53"
    "56 8B 74 24 0C 68 96 66 50 00 C3"
)
ENTRIES = {
    "action": 0x27ab9cf,
    "action_end": 0x27aba11,
    "auto": 0x27abdd5,
    "hit_roll": 0x27abdf1,
    "crit_roll": 0x27abe35,
    "gunblade": 0x27abee4,
    "e10_hit_roll": 0x27abe76,
    "e10_crit_roll": 0x27abead,
    "e10_auto_crit": 0x27abed0,
    "defer": 0x27ac02f,
    "contact": 0x27ac0f1,
    "swing": 0x27abfb4,
}


def _assemble() -> tuple[bytes, dict]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])

    import re
    defined = re.findall(r"^([a-z_0-9]+):$", ASSEMBLY, flags=re.M)

    def entry(label: str) -> int:
        # Assemble up to the label. A call from there to a routine defined
        # further on (input calls judge_slot) is a fixed rel32, so a stub for
        # it after the label does not move anything before it.
        prefix = ASSEMBLY.split(f"\n{label}:")[0]
        stubs = "".join(f"\n{name}:\n nop" for name in defined
                        if name != label and not re.search(rf"^{name}:$", prefix, flags=re.M))
        offset = len(ks.asm(prefix + f"\n{label}:\n nop" + stubs, CAVE)[0]) - 1 - stubs.count("nop")
        return CAVE + offset
    entries = {label: entry(label) for label in ENTRY_LABELS}
    for label, address in entries.items():
        first = ASSEMBLY.split(f"\n{label}:\n")[1].splitlines()[0]
        if not re.search(r"\b(call|j[a-z]+)\b", first):
            expected = bytes(ks.asm(first, address)[0])
            assert code[address - CAVE:address - CAVE + len(expected)] == expected, label
    return code, entries


def _bounded(value, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number from {low} to {high}")
    if not low <= value <= high:
        raise ValueError(f"{label} must be from {low} to {high}")
    return value


def data_bytes(window_ms: int, success_sound: int, crit_sound: int, failure_sound: int,
               continuous: bool = False) -> bytes:
    values = (window_ms, window_ms * EARLY_FACTOR, int(continuous), success_sound, crit_sound,
              failure_sound, 0, 0, 1000, 0, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0, 0,
              0, 0, 0, 0xFFFFFFFF, 0, 0xFFFFFFFF)
    head = b"".join(value.to_bytes(4, "little") for value in values)
    # The whole block, held-result slots included, is written: the cave sits in
    # .rsrc, whose bytes are icon data, and a slot must start empty.
    return head + bytes(DATA_SIZE - len(head))


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
        f"{DEFER_CALL:X} = {_call(DEFER_CALL, ENTRIES['defer']).hex(' ').upper()}",
        f"{SWING_CALL:X} = {_call(SWING_CALL, ENTRIES['swing']).hex(' ').upper()}",
        f"{CONTACT_HOOK:X} = {_jump(CONTACT_HOOK, ENTRIES['contact'], len(CONTACT_ORIGINAL)).hex(' ').upper()}",
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
    return [(INPUT_HOOK, INPUT_ORIGINAL), (DEFER_CALL, _call(DEFER_CALL, APPLY)),
            (SWING_CALL, _call(SWING_CALL, START_SEQUENCE)),
            (CONTACT_HOOK, CONTACT_ORIGINAL),
            (ACTION_HOOK, ACTION_ORIGINAL), (ACTION_END_HOOK, ACTION_END_ORIGINAL),
            (AUTO_HOOK, AUTO_ORIGINAL), (GUNBLADE_HOOK, GUNBLADE_ORIGINAL),
            *((site, _call(site, RANDOM)) for site in (HIT_ROLL_CALL, CRIT_ROLL_CALL, E10_AUTO_CRIT_CALL,
                                                       E10_HIT_ROLL_CALL, E10_CRIT_ROLL_CALL)),
            *((site, original) for site, original, _ in TRIGGER_STORES)]
