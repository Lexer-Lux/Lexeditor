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

## Damage is applied before the hit lands

- The command resolves damage, caps it (`00491124`), stores the result in
  `01D27AE4`, and calls `00494410`. That function writes the target's new
  current HP (`+0x18`, at `004946BC`) straight away. The animation later only
  displays the stored number.
- Consequence for Timed Blocks: a press during the enemy's swing cannot
  change the damage at its source. It must refund the difference to HP at
  the hit frame and correct the displayed number.

## Hit records handed to the animation

- `0048EF80` appends one 0x18-byte hit record per target to the queue at
  `01D28344` (count `01D280C1`): target at +0, effect/flag bytes at +1..+3,
  damage word at +6, then the second-effect fields.
- `0048E396` builds the action packet the animation receives. Its `+8`
  points at the first hit record for this action. The animation side walks
  those records to show numbers; the opcode that does so is not yet traced.
- Neither FFNx's `ff8.h` nor ff8-decomp (the PS1 build, battle interpreter
  not yet decompiled) names this display path.

## Not yet established

- Which sequence opcode marks the moment damage is displayed (the hit frame)
  for enemy and party sequences. `0x91` (`00505362` → `0048AE60`) and `0x9D`
  (`0048ADF0`) are the only opcodes that call into battle logic. Neither is
  proved to be the hit frame.
- Which physical button reaches R1 under Modern Controls, and whether the ATB
  menu also consumes that press.
