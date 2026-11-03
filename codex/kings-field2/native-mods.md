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

Lexeditor deploys owned source folders prefixed lexeditor-. It preserves other
native mods, refuses replacement of externally edited deployed source, and
journals native flags and copies for recovery. The adapter requires a closed
game. It does not edit settings.json, memory cards, disc data or game binaries.

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

Creature records start at `0x8016C544`, stride `0x7C`, with 200 slots. Current HP is `u16+0x1A`;
spawn `0x80039AFC` copies its maximum from definition `0x80172624 + type*0x78 +0x1A`.
Damage `0x8003A9CC` follows linked body parts to their parent before subtracting HP.
Hit Feedback measures the resulting loss against that definition maximum.
Its only setting is maximum flash duration in seconds (0–5, default 0.6).
Duration is that maximum times min(actual HP lost / definition maximum HP, 1).
The native check confirms a 1-second maximum and 10% loss give 0.1 seconds.

Native running `0x8002957C` subtracts 500 per 15 Hz world tick from both 5000-point
physical/magic power gauges `0x8019942E` and `0x80199432`. Better Sprint changes this charge only
after actual collision-resolved horizontal movement. Empty power also requires
removing positive carried run acceleration at `0x80199422`, not merely clearing the
run input bit. There is no separate added stamina pool.

Forget Me Not uses actual interaction, lock, empty-search and pickup results.
Its sidecar binds exploration to card path, slot and native save-block hash.
It keeps original/newest snapshots per card/slot, capped at 12 snapshots and 8 MiB.
It excludes the native secret-door behavior `0xFF` rather than marking every door.

## Fire Crystal and the two magic menus

Fire Crystal is item 90. Its native handler learns Fire Ball (spell 7) before
consuming the item. Offensive magic 0..13 is equipped through Equipment/Magic.
Use Magic lists support spells 14..19. An empty Use Magic menu therefore does
not establish failed Fire Crystal learning. This distinction was confirmed by
the player's learned Fire Ball flag and by original-port menu-use reproduction.
