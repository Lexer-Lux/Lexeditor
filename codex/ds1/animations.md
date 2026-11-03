# DS1 animation events (TAE1)

Proven by read-only inspection of the installed Remastered game:
270 `.tae` files in every readable `chr/*.anibnd.dcx`, 15161
animations, about 200000 events. Container layout translated from
SoulsTemplates' Apache-2.0 TAE3 templates; event meanings paraphrased
from the soulsmodding wiki (CC BY-SA) and confirmed against measured
value distributions. See `plugins/ds1/credits.md`.

## Container (all offsets little-endian, 32-bit)

- Magic `TAE `, version `0x1000B`, header constants
  `0x40/1/0x50/0x70`, file size at 12. 64-byte header.
- Block at 80: file ID, animation count, animation table offset,
  animation-group table offset, `0x90`, count again, first animation
  data offset. Skeleton/SIB names are wide strings.
- Animation table entry: ID `u32`, data offset `u32` (8 bytes).
- Animation data (28 bytes): event count, event header offset,
  group count (always 0 in DS1), group offset (always 0), timestamp
  count, timestamp pool offset, animation-file offset.
- Event header (12 bytes): start timestamp offset, end timestamp
  offset, event data offset. Timestamps are `f32` seconds in the
  pool, usually 30 Hz ticks.
- Event data: type `s32`, parameter pointer `u32`, then parameters.
  The pointer is always data+8 when parameters exist, 0 when the
  event is empty. 58 types observed; each has a fixed size (see
  `EVENT_TYPES` in `plugins/ds1/tae.py`).

## Editing facts

- Timestamps live in one shared pool per animation: 40% of slots are
  shared by several events (up to 20). Editing a timestamp moves
  every event that points at it; the UI names the sharers.
- Timestamps may be negative and an end may precede its start; both
  occur in vanilla data and stay valid.
- Animations may carry zero events and no name (name offset at end
  of file); those are placeholder entries.
- Empty events (parameter pointer 0) occur, mostly type 16. Their
  parameters stay hidden; timing still edits.
- Types 8, 16, 228, 233, 301 and 308 have unconfirmed layouts and
  stay read-only apart from timing.
- Nine binders cannot be opened: eight use a non-`0x74` BND3 flavor
  and `c3471.anibnd.dcx` holds two members named `c3471.tae`. Fifty
  further binders (LOD models) hold no `.tae` at all.
- This version edits event values in place only. Adding or removing
  events would shift TAE-internal offsets, which is not implemented.
  Mods merge at member granularity: same-size member swaps splice
  into vanilla bytes, resized members rebuild the binder, and only
  added or removed members fall back to whole file, last mod wins,
  with a conflict entry.
- Rebuilt binders follow the shipped layout, measured over every
  readable character binder and the parameter binder: stored names
  packed tight, data starting on a 16-byte boundary, each non-empty
  payload aligned to 16, empty members (the `delay_*.txt` markers)
  sitting tight after the previous payload, no trailing padding.
  Rebuilding a binder with unchanged bytes reproduces it exactly.

## Cross-links

- Attack events (type 1) name an attack slot and behavior key; the
  slot indexes the same `AtkParam_Npc` rows the Attacks tab edits.
- Adding-effect events (types 66, 67, 302, 401) point at
  `SpEffectParam` rows by ID; every vanilla value resolves.
- Dummy-poly fields name skeleton nodes by ID, the same numbering
  the hitbox `DmyPoly` fields use.
- Character labels come from map placements: the enemy most often
  placed with a `cXXXX` model names that character. 148 of 157
  animated characters resolve. `c0000` is the player: 76 of 77
  player-start placements use it (one uses `c2020`).
