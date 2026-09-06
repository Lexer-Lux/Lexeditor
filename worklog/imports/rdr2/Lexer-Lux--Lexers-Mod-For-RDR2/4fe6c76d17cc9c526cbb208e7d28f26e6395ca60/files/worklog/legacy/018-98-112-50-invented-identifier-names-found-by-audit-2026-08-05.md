# Worklog: 018 98 112 50 Invented Identifier Names Found By Audit 2026 08 05

## #98 / #112 / #50 — invented identifier names, found by audit 2026-08-05

ROOT CAUSE CLASS, not three separate bugs. `joaat()` hashes whatever string it
is handed; a name the game does not define hashes to a value nothing matches and
the call becomes a silent no-op. Nothing warns. Audited every `joaat("NAME")`
literal in `script.cpp` (140 of them) against the full decompiled corpus plus the
unhashed-strings dump (1.28 GB, case-insensitive because our joaat lowercases).

Truly absent from the game, excluding our own LEX_*/PICKUP_LEX_* definitions:

  INPUT_HOLSTER_WEAPON     #98 - the whole feature's trigger
  INPUT_HOLSTER            in a disable-list (binoculars) and a name table
  INPUT_HOLSTER_ATTACH     same
  INPUT_TAKE_COVER         in a disable-list
  INPUT_ENTER_COVER        same
  MARKER_TYPE_CYLINDER     #112 tracers and #50 bloodstain marker

Real names, from Rockstar's own scripts: `INPUT_TOGGLE_HOLSTER` (421 files),
`INPUT_COVER` (411) / `INPUT_COVER_TRANSITION`.

Marker type: Story Mode never calls `_DRAW_MARKER`; MP does, and every literal
call passes `-1795314153` = `0x94FDAE17`, with scale 0.4/0.4/1.25 and p19=2 —
a tall thin vertical cylinder, and the same p19 our code already passed. Adopted
as `kMarkerVerticalCylinder`. `MARKER_TYPE_CYLINDER` hashes to 0x29C3F618 and
matches nothing.

Animation literals were audited the same way (20 dictionary/clip strings) and
ALL 20 exist in the game data — so #169 / #116 / #85 are NOT this bug class.

#98 rebuild. Removed the 450 ms grace period and the unknown native
`0xBDD9C235D8D1052E`, which was being treated as "is already holstered" on no
evidence and sat on the critical path.

Weapon state is an ATTACH POINT, not a flag. Derived the slot map by bucketing
every literal `SET_CURRENT_PED_WEAPON(ped, joaat("WEAPON_*"), _, N)` call in
`script_rel`: 0 in use (all families), 1 off-hand, 2/3 right/left hip holster
(revolvers only), 4 knife sheath (knives only), 7 bow sling (bows only), 9 and
10 the two longarm slots (repeaters/rifles/shotguns only). Clean separation by
weapon family across thousands of call sites, so the mapping is sound.

New `updateAlwaysHolster`: fires on the `INPUT_TOGGLE_HOLSTER` press edge, reads
attach points 9 and 10 via `GET_CURRENT_PED_WEAPON(ped,&h,TRUE,point,FALSE)`,
and only acts when the current weapon is one of those two longarms — sidearms
untouched so the toggle can still DRAW. Put-away uses `_HIDE_PED_WEAPONS`
(0xFCCC886EDE3C63EC), documented as "unequip current weapon and set current
weapon to WEAPON_UNARMED", i.e. the fists path Lexer confirmed works.
`[AlwaysHolster] Log=1` records held/slot9/slot10 per press if the slot theory
needs confirming in game.

Built exit 0 (only the pre-existing C4838 at script.cpp:1839). Installed with
the game closed, hash-verified
`418375347DB695071E0AE4E449163569D18A4FE2303EBB1DA51B06109765556C`.


