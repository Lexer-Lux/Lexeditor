# Timed hits and blocks (issues #482, #483)

Static findings against `FF8_EN.exe` SHA-256 `064d466b…9570`. Addresses are
absolute VAs; file offset = VA − `0x400000`. Battle participants are
`0x01D27B10 + index * 0xD0`.

## The trigger window lives in the animation sequence

- Sequence opcode **`0xAB`** opens Squall's trigger window. The dispatcher at
  `00504BE3` subtracts `0x80` and indexes the table at `005056C8`; entry 43 is
  `00504E50`. The opcode reads two argument bytes, then a list of timing
  bytes up to `0xA1` (with `0xA0` separating groups), stores them at
  `01D98214`, and starts the trigger task (`004BA4C0`, `004BA560`).
  Squall's weapon sequences carry it, e.g. `ab 00 21 23 27 28 a0 29 24 25 26 a1`
  (smalldirt's section-5 dump on qhimm). No other character's sequences do.
- The trigger task `004BA6C0` runs each frame as battle-menu task 6. At
  `004BA88A` it tests the trigger button (`dl & 0x08`). A press is recorded
  once per hit as quality = elapsed frame + 5 (`01D7679C`). `0048FE10` accepts
  it when quality ≥ 20. `004BA566` suppresses the on-screen bar when
  `[01CFE978] & 0x8001` is set. ff8-memory independently confirms this
  window: RENZOKUKEN_DIFF runs 0→27 and a press around 15 hits (`0x1976794`
  there = `01D76794` here; its offsets omit the `0x400000` base).
- Bit `0x08` is R1. ff8-memory's controller map lists L2, R2, L1, R1 as the
  first four pad buttons, which is the PlayStation pad's bit order.
- On success the task sets `01D9821E`. The sequence engine (`00504449`) then
  spawns effect `0xF1` through `00502170`/`00501640`: this is the native
  success cue.
- After each hit `004BA935` calls `00485130(hit, total, quality, 0x20)`, which
  stores `01D28D90/92/94/96`.

## How the bonus is gated to Squall

- Only damage type 10 (gunblade), reached from the damage switch at
  `004922E0` → `0048F480`, reads the quality. Damage is the normal physical
  formula times `(2 + quality/20) / 2`. A successful press (quality 20–25)
  therefore gives ×1.5; no press gives ×1.
- `0049101F` marks quality ≥ 20 as a critical display (`01D27ADE = 2`).
- Everyone else's Attack is damage type 1 and never reads `01D28D94`.
- So there are two gates: the `0xAB` opcode exists only in gunblade
  sequences, and only type 10 applies the bonus.
- Not the trigger: the ×1.5 at `0049104C` tests persistent-status bit `0x20`
  (Berserk). `+0x90` is the persistent status byte (`0x08` Darkness,
  `0x20` Berserk, `0x40` Zombie).

## Damage lands during the animation

- A hit-frame log with HP on every line (Lexer's session, 2026-09-26) shows
  targets' current HP (`+0x18`) dropping mid-animation, at a frame boundary,
  never when the command is chosen. An earlier reading of this page said HP
  was written at the command; the log disproves it.
- The drops sit between animation frames, not right after one opcode: the
  battle step applies the hit from a queued task. `0048F3F0` and `0048F350`
  (queued through `0047E200` at `00485D46`/`00485D6B`) walk the action's hit
  records and call `0048FE20(target)` then `0048EF80` for each; `00485160`
  does the same for the gunblade trigger path, and `004850A0` for a
  button-mash limit break. `0048FE20` reaches `00494410`, which writes HP
  (`004946BC`).
- So the hook for Timed Hits and Blocks is `0048FE20`: it runs for every
  attacker at the moment damage lands, and a press shortly before it can
  scale that hit. The hit-frame log's `FFFFFFFF` lines record each call to
  confirm the timing in game.

## Hit records handed to the animation

- `0048EF80` appends one 0x18-byte hit record per target to the queue at
  `01D28344` (count `01D280C1`): target at +0, effect/flag bytes at +1..+3,
  damage word at +6, then the second-effect fields.
- `0048E396` builds the action packet the animation receives. Its `+8`
  points at the first hit record for this action. The animation side walks
  those records to show numbers; the opcode that does so is not yet traced.
- Neither FFNx's `ff8.h` nor ff8-decomp (the PS1 build, battle interpreter
  not yet decompiled) names this display path.

## Hit and crit rolls (2026-09-27)

- Physical types reach `00492339` (and the similar callers at `00492470`,
  `004924FA`, `00492682`): `00492B00(attacker, target)` returns 1 for an
  automatic hit (target status flags `& 9`, or hit rate `[01D2A238]` = 255);
  otherwise `00492BA0` rolls. A failed roll jumps to `004926B0`, which sets
  the miss mark (`01D27ADE` bit 4) and deals nothing. Then `00492B30` rolls the
  crit and, on success, sets `01D28E07` and the crit mark (`01D27ADE` bit 2).
- Hit roll: `esi = max(0, hit rate + attacker LUCK/2 − target EVA − target
  LUCK) × 255 / 100`; the hit lands when `esi ≠ 0 && esi ≥ random & 0xFF`
  (`call 0048F020` at `00492C15`). No cap at 100: above 255 always hits.
- Crit roll: `esi = (attacker LUCK + [01D2A23B]) × 255 / 256`, the same test
  (`call 0048F020` at `00492B6C`).
- Types 34 and 36 go to `00492E10`, the same rolls with the threshold in EDI,
  attacker × 0xD0 in ESI and target × 0xD0 in EBP: automatic hit → crit roll
  only at `00492EA3`; hit roll at `00492F29`; crit roll at `00492F71`; miss
  exit `004930CB`. Full LUCK Accuracy (`luck_accuracy.py`) patches only this
  routine (`00492EEF`), so ordinary Attack (type 1, `00492BA0`) keeps LUCK/2
  even with it on.
- Squall's gunblade handler `0048F480` never rolls a hit. `0048F52A` clears
  `01D28E07`, and `0048F652` doubles the damage when it is set. `0048F522`
  (`xor eax, eax; pop ebp; ret`) is its no-damage exit.
- Squall's hit lands through `00485160` when his trigger task closes a
  window at frame 27 (`004BA8F5` → `00485130` stores the hit counter
  `01D28D90`). His earlier normal-path call to `0048FE20` (from `0048EA93`)
  deals no damage: in the 2026-09-27 hit-frame log every `004851F6` landing
  is preceded by a `0048EA98` call on the same target that leaves its HP
  unchanged.
- Timed Hits (redesign) replaces the random byte at all five roll sites with
  the timing verdict, and judges Squall at `0048F530` only while `01D28D90`
  is set.

## What releases a hit (2026-09-27, static; for the time indicator)

The time indicator needs a hit's landing time before it lands. Static trace:

- The battle step queues the action, then the damage. `00485CE7` calls
  `0047E3F0(0x68, 0x80, action)`: message type 0x68 (104) in the animation
  scheduler queue at `01D96D68`. Then `00485D46`/`00485D6B` call
  `0047E200(0048F350 or 0048F3F0)`, which is `00500DF0(10, 0x80, func)`:
  message type 10 with the damage routine.
- The scheduler `00500CC0` dispatches messages in order. A dispatched
  message raises the current level to its priority (`[B8A3F0]`), so a later
  message of the same priority (0x80) waits until the earlier one's state
  byte (`+1`) becomes 0x0F/0xFF. Type 10 is `00500A3D`: it calls the function
  at once. So damage lands the moment the action message is released.
- Type 0x68 goes through `00502380` to `0050A790`, which picks a task by the
  action kind (`[01D99A50] + 1`, table `0050A89C`/`0050A878`): kind 2 →
  `0050B2A0` (physical, unless `+4` is 0x46 or 0x0F → `0050A9A0`), and the
  others `0050BD00`/`0050BD80`, `0050B830`, `0050B0C0`, `0050BDC0`,
  `0050BEE0`, `0050BB00`, `0050B190`, `0050BC20`. The task keeps the message
  at `+0x10` and releases it with `mov byte [msg + 1], 0xFF`.
- The physical task releases at `0050B7C8`, in its last state, after
  `01D97718` is 0. `01D97718` is a bit per animation object with an active
  motion path: the path interpolator around `005035E0` clears the object's
  bit (`0050375B`) when its last key is reached. `0050B190` (spells and
  effects) releases at `0050B266` once `0050AE80` reports every sequence
  owner idle, the effect module done (`[01D96AAC]` = 0) and no motion path.
- So a physical hit probably lands when the attacker's motion path ends,
  and a spell when its effect ends. A path's keys are known when it starts,
  which would let the indicator predict the landing time. Not yet shown: which
  path an Attack waits on, how many frames separate its end from the damage,
  and the frame rate these counts use. That needs a runtime log of
  `01D97718` and the physical task's state (`[task + 0xD]`) next to the
  existing `0048FE20` lines.

## Not yet established

- Which sequence opcode marks the moment damage is displayed (the hit frame)
  for enemy and party sequences. `0x91` (`00505362` → `0048AE60`) and `0x9D`
  (`0048ADF0`) are the only opcodes that call into battle logic. Neither is
  proved to be the hit frame.
- Which physical button reaches R1 under Modern Controls, and whether the ATB
  menu also consumes that press.
