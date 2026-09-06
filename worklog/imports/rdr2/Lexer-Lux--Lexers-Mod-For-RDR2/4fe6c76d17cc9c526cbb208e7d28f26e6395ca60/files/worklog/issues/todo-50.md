# Worklog: Todo 50

## #50 lost-money marker: icon, scale, world marker — 2026-08-05

Three complaints, three separate causes, all in `updateBloodstain` /
`createBloodstainBlip` in `GameplayTweaks/script.cpp`.

MAP ICON. It was `BLIP_AMBIENT_DEATH`, which is the small outline CROSS — a
grave marker for a death the player recovered from, conveying nothing about
money. Now `BLIP_CASH_BAG`, the shipped money-bag-with-a-$ sprite. Confirmed a
real sprite, not just a decompiler symbol: `net_coach_holdup.c` calls
`MAP::SET_BLIP_SPRITE(..., joaat("BLIP_CASH_BAG"), false)`, and
`MyOverhaul/blipdata.ymt:880` has the entry with `TextureDictionary blips`.
Side effect worth keeping: this frees the cross for #147g, which explicitly
asks for the bloodstain's cross icon on graves.

NO SKULL EXISTS. Checked every one of the 321 extracted textures under
`GameplayTweaks/icons/vanilla/png/blips/`. Nothing skull-shaped in the SP set at
all. Not "probably not" — the full list was enumerated. A skull is therefore new
art through the `lex_blips.ytd` pipeline (#8/#147 prove that pipeline works), so
it is a C-suffix task, not a code one.

ICON SIZE. Nothing had ever called a scale native, so it drew at the same size
as every ambient blip. Added a `SET_BLIP_SCALE` wrapper (0xD38744167B2FA257,
present in the SDK header) and set 1.4 by default.

WORLD MARKER. It was dim by construction: an 0.8 m pool at RGBA 105,0,0,190 and
a 0.10 m wide, 1.5 m tall beam at 170,20,0,105 — dark red on ground that is
frequently already dark. Now 1.6 m gold pool at 220 alpha, a 0.26 m x 3.2 m
gold beam, and a `DRAW_LIGHT_WITH_RANGE` at the spot so it is findable after
dark. Still `0x94FDAE17` for the cylinder: that shape is world-VERTICAL, which
is the defect that killed the #112 tracers and is exactly right for a fixed
ground marker.

New `[LostMoney]` ini section — `MapIcon`, `MapIconScale`, `PropModel`,
`WorldMarkerScale` — so the alternatives can be tried without a rebuild. The ini
read lives in `loadBloodstainSettings()`, forward-declared near the other
loader forward declarations because the state it fills is defined much further
down the file.

Prop left at `p_moneybag01x`. Verified alternatives exist in the archive item
list if it still reads too small: `p_moneybag05x`, `p_satchel01x`,
`p_strongbox01x`, `p_chest01x`.

Built clean (two pre-existing C4838 warnings at script.cpp:1983, unrelated) and
installed with the game closed; asi/ini hash-verified. UNVERIFIED in game: the
new sprite renders, the scale is visible on the map, and the gold marker reads
from a distance and at night.


========================================================================
#147 COLLECTIBLES ON THE MAP — a, b, e, g
========================================================================

(a) DINOSAUR BONES INVISIBLE ON AN EXISTING SAVE.
Lexer assumed a one-time quest-start trigger and blamed his own save. Neither
was true. `collectibleUnlocks()` is polled once a second from the main loop, so
progress WAS being re-read at startup and continuously after; the check itself
was wrong. It asked `hasOrUnlocked("DOCUMENT_NOTE_DINO_BONES")` — is the
quest-starting note in the inventory — and on a save that started the hunt long
ago it is not: the note is read and gone, and `UNLOCKED()` does not cover
documents. His own `GameplayTweaks.probe.log` is the proof: `CATEGORY DINO_BONES
sub=0 -> num=30 found=2` while the document check returned nothing.

Fix: `collectableCategoryStarted()` wraps CATEGORY_GET_NUM_FOUND
(0x5461C821D00FE15A) — value-return, no output pointer, safe to poll — and each
of the four ledger-backed categories now unlocks on `document OR found>0`.
Category name strings taken from the probe log, not guessed: `CIGARETTE_CARDS`,
`DINO_BONES` (NOT `DINOSAUR_BONES`, which returns nothing), `ROCK_CARVINGS`,
`LEGENDARY_FISH`. Exotics have no ledger entry in story mode so they stay
document-only — recorded as #210 rather than papered over.

(b) DREAMCATCHERS STACKED ON ONE SPOT — IDENTITY WAS NOT UNIQUE.
All 20 dreamcatcher rows are named "Dreamcatcher"; 19 exotic names repeat too
(20x "Gator Eggs", 20x "Moccasin Flower Orchid", ...). `collectibleKey()` was
`category|name`, and `applyCollectibleFixups()` matched the same pair, so a
single F3 nudge line rewrote the coordinates of ALL 20 dreamcatchers onto one
point. His installed `collectibles_fixups.csv` had exactly two dreamcatcher
lines — that is the pile. The same defect made one collected exotic retire every
other spot for that flower.

`CollectibleMarker` gains `index`, the 0-based occurrence within
(category, name), assigned in `loadCollectibles()`. Keys are now
`category|name|index`. Both state files stay readable: a legacy collected line
without an index applies to index 0 only (for the 8 categories with unique names
that is lossless; for dreamcatchers/exotics the row is genuinely ambiguous and
nothing else is honest), and `applyCollectibleFixups()` sniffs field count —
5 fields is the new indexed form, 4 is legacy and lands on index 0.
`relocateNearestCollectible()` writes the indexed form.
His two dreamcatcher nudge lines were unattributable, so the installed file was
backed up to `collectibles_fixups.csv.bak-147b` and those two lines removed;
the card and bone lines were left alone.

(e) GRAVES OF LIVING PEOPLE.
All 8 graves belong to gang members who die during the story and nothing gated
them. Added an optional 5th `require` column to `collectibles.csv` holding a
story-mission id, checked with MISSIONDATA_WAS_COMPLETED (0xE54DC27571D5EDC4).
That native's arg shape is confirmed by Rockstar's own code:
`script_rel/medium_update.c:2347` calls it as
`MISSIONDATA_WAS_COMPLETED(joaat("MUD1"))` — one id hash, value return.

The original conservative `FINALE3` gates were replaced for #212 after mapping
the death missions directly from the decompiled mission scripts and their
mission-local label prefixes: Davey=`WNT1`, Sean=`GRY3`, Kieran=`MOB3`, Hosea
and Lenny=`NBD1`, Eagle Flies=`NTS3`, and Susan and Arthur=`FIN1`. The matching
scripts contain the death scenes themselves (`grays3.c` has Sean's death anim,
`mob3.c` the headless Kieran scene, `saint_denis1.c` the bank deaths,
`native_son3.c` Eagle Flies, and `finale1.c` Susan and Arthur). This made the
F10 completion probe unnecessary for the mapping; it remains available only as
a diagnostic if a gate ever fails in game.

(g) `categoryIcon("grave")` now returns `BLIP_AMBIENT_DEATH`, the shipped
outline cross — the icon #50 moved OFF for the bloodstain, which is what Lexer
asked for. `LEX_BLIP_GRAVE` is no longer referenced by code; its blipdata entry
and texture are dead weight, noted in #209 for the next art rebuild.

c/d/f spun off as requested: #209 (icon artwork, Class_B), #210 (exotics test),
#211 (fish test). #212 covers tightening the grave gates.

Built clean (the two pre-existing C4838 warnings, now at script.cpp:2091) and
installed with the game closed; asi/ini/csv hash-verified. UNVERIFIED in game:
bones now appear, dreamcatchers are spread out, no grave icons before the
epilogue, and graves draw as a cross.

