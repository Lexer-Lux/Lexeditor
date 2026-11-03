# King's Field II native source mods

Japanese numbering: this plugin targets the English SLUS-00158 disc, sold in
North America as King's Field. SLUS-00255 is Japanese King's Field III and uses
different addresses. The port recompiles the player's disc locally.

Source fork: [Lexer-Lux/verdite2](https://github.com/Lexer-Lux/verdite2).
Independent module distribution: [Lexers-Mod-For-KF2](https://github.com/Lexer-Lux/Lexers-Mod-For-KF2).
Fork API and controls are documented in its docs/LEXER_FORK.md. Gameplay module
payloads belong in the user's mod library and that distribution repository.

## Settings, deployment and loader

Native data defaults to LocalAppData/Verdite2. VERDITE2_DATA selects another
data directory for both the native port and editor adapter.
Diagnostics must point both at the same private copy when using both processes.

Native gamepad yaw and pitch default to3; explicit saved sensitivities and
bindings survive startup, including configurations predating the old defaults
marker. At sensitivity1, the hooked native look routine produces35 yaw units per
tick standing,28 moving, and32 pitch (4096 units per revolution,15Hz world).
Sensitivity3 produces105/84/96, below the port's x4 ceiling, so the proportional
enemy-turn ratio is3/1. Existing native turns toward the player get x3 top speed
and x9 acceleration by default. The measured chase baseline11/4 becomes33/36;
a quarter turn takes94 ticks originally and32 compensated. Non-player turns
retain their timing; other creature fields remain unchanged. Extra standing
tracking defaults off, and explicit enemy-turn/tracking preferences are retained.

The native loader enables IDs through interface.ini, section RecompOne,
mods.<id>.enabled=True. settings.json's legacy ActiveMods array is not read to
enable mods. Native source mods implement IMod.OnLoad; optional OnUnload and
DrawSettings add cleanup and a gear panel. Do not provide an empty DrawSettings
override: it creates an empty gear panel. Dependencies load first; other entries
use native ID order. The library's presentation order does not control this.

Lexeditor edits the native writable mods directory in place through the shared
NativeSourceModAdapter. There is no second Documents library or prefixed deployed
copy. Native loader flags remain the single enablement store. Mutations require
a closed game; settings.json, memory cards, disc data and game binaries are not
mod deployment targets. The native content/mods directory only seeds bundled
mods; it is not the player library.

## Extended scenery range

Fork preview4 accepts10.5..30 tiles in half-tile steps. View distance and smooth
distance fade use separate keys, `kf2.renderdistance` and `kf2.distancefade.on`.
Distance scales retained-world fog by distance/10.5; the optional fade only
adds a one-tile transition at the boundary. Changing fade does not change reach.

The current area's entire80x80 map is already resident. Extended reach selects
more of that geometry; it does not stream adjacent areas. Retained GPU placement
uses full coordinates before the old signed16 packet path. Unsupported packet
fallbacks outside signed16 placement are skipped, preventing coordinate wrap.
Without retained GPU geometry, effective reach stays at15 while preserving the
saved larger preference. Extended reach therefore requires GPU geometry.

The GPU depth representation ends at65536. Above15 tiles, a separate mandatory
depth guard fades out over62976..65024 even when the optional distance fade is off.
Main, mirror and retained reflection passes receive the physical depth guard;
the first-person arm and sky keep their existing exclusions.

An installed preview4 matched-camera capture in the native fdat02 corridor
selected106 map halves at15 and173 at30, including67 beyond15.5. Real geometry
extended to27 tiles in that corridor, with visible added floor/walls. A pitched
capture selected real vertices to66688 view depth while retaining the65024 guard.
These establish this area's renderer behavior, not coverage of every map or
every optional legacy renderer configuration.

Native setup has one Controls category containing Control layout, Movement and
Rumble and gyro. Turning and difficulty remains separate. Both initial setup
and rerun traverse six numbered steps. Classic/Modern/Keep choices share that
category; saved custom bindings and sensitivity are preserved on ordinary boot.

## Original notification rendering

Fork v0.5.3-lexer.2 adds NativeNotifications.Post(owner,glyphs), PostText,
Flush and Cancel. Independent mods share the eight-slot native queue. Equal
adjacent notification IDs are coalesced by the game, so reserved IDs 232..239
correspond to queue slots. Cancel preserves other owners and vanilla messages,
including their coin amounts. Source mods cancel their owner on unload.

Native enqueue is `0x80033F08`, controller `0x80033FBC` and toast drawing `0x80033E78`.
Original font drawing is `0x80021E10`. The font reads cursor `0x8006E914`; its allocator
advances that cursor and active descriptor `0x8017E0A4`'s `+8` pointer. HUD extensions
must maintain both pointers or later text can overwrite earlier packets.

Better UI hooks initial pickup placement `0x80046C64` only at return sites `0x8004857C`
and `0x80048610`, after native lock/quest guards. The item record is at caller `SP+0x80`.
Item names are original-font bytes at `0x80065B24`, stride 24 bytes. Native gold feedback
remains unchanged. Poison notifications belong to Better Poison, not Better UI.
The real native confirmation loop was held for 2.5 seconds before choosing an
action. The name rendered with nonzero native brightness while inventory was
zero and the ground item was still present. Taking acquired it; putting away
did not. Disabling only Better UI removed the name and retained those choices.

## Damage, power and exploration

Loose-pickup eligibility uses definition kind `0x40`, a live behavior byte and
`record+0x38 == 0xFF`. The last condition is checked by native pickup `0x8004831C`
itself, so it must not be removed by analogy with another game's object layout.
The behavior byte at `+4` is not the definition kind: actual loose item/gold
records can carry `0x10`/`0x62`. Container-linked items remain manual. In an
installed preview4 private run, untouched retail item91 and gold70 collected
through the normal mod/native path after moving only the player to their actual
positions. Inventory rose0→1 and gold72→73; no item fields or restrictions were
rewritten. This supplements the capacity, quest and container fixture checks.

Creature records start at `0x8016C544`, stride `0x7C`, with 200 slots. Current HP is `u16+0x1A`;
spawn `0x80039AFC` copies its maximum from definition `0x80172624 + type*0x78 +0x1A`.
Damage `0x8003A9CC` follows linked body parts to their parent before subtracting HP.
Hit Feedback measures the resulting loss against that definition maximum.
Maximum flash duration is configurable in seconds (0–5, default 0.6).
Duration is that maximum times min(actual HP lost / definition maximum HP, 1).
Peak strength is (1 - HP after the hit / definition maximum) times the red
intensity setting (0–100%, default50%). Each damaging hit replaces the current
pulse and linearly fades to zero. Healing and zero damage do not restart it.

Preview5 exposes generic captured ModelInstance.ColourMixRgb/ColourMix fields.
The retained GPU colour pass mixes final textured, lit and fogged RGB toward the
target before quantization, preserving alpha, holes, blending and depth. Native
RGBC multiplication cannot make a green texel with zero red become red. Hit
Feedback edits only its draw's new main/mirror instances, with frame identity and
nested-draw guards; world mirror replay is included and previews excluded. It
requires the supported retained GPU model path. No native RAM/GTE lighting is
changed and there is no brown modulation substitute on unsupported renderers.

Actual native damage220->148 on the existing220HP plant gives981ms at a3-second
maximum. Private GPU captures show zero/37.5%/full-red endpoints and an actual hit
fading back to green; the partial/full captures have no changed pixels outside
the expanded creature region. Animated quantized captures do not establish a
same-texel numeric weight comparison.

Native running `0x8002957C` subtracts 500 per 15 Hz world tick from both 5000-point
physical/magic power gauges `0x8019942E` and `0x80199432`. Better Sprint changes this charge only
after actual collision-resolved horizontal movement. Empty power also requires
removing positive carried run acceleration at `0x80199422`, not merely clearing the
run input bit. There is no separate added stamina pool.
Running consumes no magic power by default; disabling that option charges the
native magic-power gauge too. MP and legitimate casting/item costs remain native.
Exhaustion latches until release and a fresh run press. Native load, full reset
and menu handling preserve that latch for an input still held. Scripted physical
keyboard/controller events through the real mapping routines exercise both
Classic and Modern paths; this is separate from human controller feel.

Forget Me Not uses actual interaction, lock, empty-search and pickup results.
Its sidecar binds exploration to card path, slot and native save-block hash.
It keeps original/newest snapshots per card/slot, capped at 12 snapshots and 8 MiB.
Successful native save `0x80023764` writes the actual selected slot to
`0x8006E5D4`. A new-save request can be zero or another absent slot, and the game
chooses the first free slot instead. Persist against that confirmed byte after
success, never the requested A0 value. Native load `0x80023638(slot)` uses the
exact requested slot; `0x8004A040` receives the packed block at buffer+0x400.
Actual copied-card writes/loads preserve locked-red knowledge, confirmed empty
searches and taken contents. Other slots and a replacement save in the same slot
do not inherit unrelated history.

The native key matcher `0x800375EC(record, key)` preserves A0 and returns1 only
on a matching unlock, writing record+0x38 to255. A post-hook removes only prior
locked knowledge2 for that supported record, returning unfinished loot to white
before opening. Merely waiting for EndUse misses this separate key-use path.
It renders small surface-following billboard glints through native packets with
registered per-corner depth. Retained GPU geometry and Z-buffer support are
required; unsupported or unlocated surfaces are omitted. Actual chest and barrel
search/take, lock, gate/door opening and external-wall occlusion were rendered.
Opened-but-unclaimed containers remain white; confirmed empty/taken clears them.

Native use dispatches on the definition kind. Ordinary container kinds8/9/21/22
can initialize record behaviorFF, so FF is not a hidden-wall/liveness predicate.
Verified ordinary doors are kind3 and the kind2 definition84 barred gate. Hidden
wall definitions82/CD, unused pedestal89 and kind5 compartments are excluded.

## Additional native feedback and wall controls

Better Poison preserves native HP damage at30 world ticks per event (0.5Hz).
The old wash coefficient2400/4096 produces native green35; default35% peak
coefficient1434 produces green21. Its default0.25Hz starts visual pulses every60
world ticks. Other rates are averaged over native two-second opportunities.
The40-tick envelope advances after the actual player-stage pacing decision;
skip decrement on a new pulse so the first native wash sees the full peak.
Pre-hooks can precede the frame-pacing gate and also run on skipped frames.
Zero quantized green contributions must skip the wash call, which otherwise
increments the native averaging count and dims unrelated tints.

Owner-scoped poison status replacement removes stale own notices while retaining
other queued owners and vanilla messages. Real antidote/expiry can report CURED;
death, native load, status reset and disable cancel owned status without a cure.
Native original-font POISON CURED was observed. Notifications remain toggleable.

XP Bar height uses1..16 native pixels, default4. It keeps full viewport width and
the absolute bottom edge; actual output at2x render scale has8/24 rows for
settings4/12. Red N modifies only the original N's four compass GT4 faces,
5/6/9/10, preserving other letters, UVs, palettes and sphere geometry.

Dragon Crystal is inventory item76, countbyte8009B578. Native player state11's
frame65 branch also requires801B3089 bit8 before consuming one and reviving at
area1. Better Crystals holds the port's automatic reload only for that eligible
death and offers the original-font/native-box choice before frame64 advances.
Revive calls the native branch. Reload calls the port's existing native loader
with8006E5D4, the slot written only after successful native save/load; it ignores
the automatic-reload slot override and never calls a save routine. No save or a
failed card read retains the choice/count. Current primary/secondary keyboard and
selected digital/analog pad bindings supply the labels. Native font runs advance
7pixels and stop at24 glyphs; longer labels need multiple runs. Private actual
revive, load, failure and disable checks preserved both baseline and working cards.

The mod display name `illusory wall` is lowercase. Independent use, attack and
walk-through booleans default to native use on, others off. Exhaustive kind2
definitions are82/84/89/CD:82/CD are wall variants,84 is a real barred gate,89 an
unused pedestal. Native Cross opening verifiedCD's original rock-textured wall.
Attack follows the actual weapon query call site. Walk-through temporarily uses
the native opened footprint only for player horizontal/floor collision queries,
restoring it before rendering or save and guarding area identity. Native WallGuard
keeps ownership of28080. All eight toggle combinations, ordinary gate exclusion,
lock refusal, floor preservation and disable restoration passed native checks.

## Fire Crystal and the two magic menus

Fire Crystal is item 90. Its native handler learns Fire Ball (spell 7) before
consuming the item. Offensive magic 0..13 is equipped through Equipment/Magic.
Use Magic lists support spells 14..19. An empty Use Magic menu therefore does
not establish failed Fire Crystal learning. This distinction was confirmed by
the player's learned Fire Ball flag and by original-port menu-use reproduction.
