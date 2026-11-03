# King's Field I native runtime

These facts apply to Japan's 1994 SLPS-00017 only. The supported installation
uses the archived C# recompilation based on upstream `529a6b4`, not the newer
C++ port or either Western game. Generated game code and disc data stay private.

## Controls and weapon power

The native `content/config/controls.json` is the one profile definition used by
the port and Lexeditor. Classic matches `KeyLayout.Layout()`, empty secondary
keyboard bindings, `new GamepadBindings()` and `DefaultAnalog()` in that baseline.
It includes the port's Western face permutation; it is not guessed PSX controls.
Modern retains Select/Tab menu and Triangle/Q equipped item or spell actions
(including maps), while adding the requested shoulder actions and held run.
The corrected Modern controller profile also maps physical Start (button 6)
to the Western Circle/menu action, matching KF2 Modern. Start does not bind
Run. Classic and keyboard bindings remain unchanged. Both native setup and
Lexeditor read that one profile asset; reapply Modern to replace an old profile.
This archive has no Remaster Editor. F2 belongs to the optional Debug Tools mod.

Retail has no sprint stamina pool or drain. Held run scales collision movement
by two before collision resolution. Lexer chose weapon power for Better Sprint
and a default drain of 100% of the full gauge per second of actual sprint
movement. Zero removes drain; the percentage is not a multiplier of a vanilla
sprint rate. Current weapon power is
u16 at `0x800A0798`, full at 5000, and is also used by attacks. Magic charge is
separate at `0x800A079C`; MP is at `0x800A0796`. The native charge recovery remains
active. A sprint policy receives actual displacement after the player stage and
the logic tick duration, independent of rendering frequency.

Native weapon-power recovery (`0x80016BC0`) adds
`2 * (floor((physicalPower << 6) / (weaponChargeRate + 1)) + 1)` per logic
tick, clamped to 5000 before Better Sprint's deduction. The inputs are physical
power u16 `0x800A07A6` and byte +1 of the equipped weapon record pointed to by
`0x800A07E8`. Short Sword's rate is 10 and Knight Sword's is 18. At power 20,
Short Sword recovers 234 per tick; at power 30 it recovers 350. A 100% sprint
drain removes 333/334 at 15 Hz, so the latter plateaus at 4666/4667 after native
recovery refills it every tick. This was reproduced at fixed position and does
not establish a location-dependent cause. Rendering at 30, 60 and 144 FPS kept
those amounts unchanged.

## Built-in death reload

`kf1.autoreload.enabled` is a native port setting, default true, shown under
F1 → Gameplay and exposed by Lexeditor. It replaces ordinary respawn at
`0x800154B0`, caller RA `0x8001869C`, only for dead state 255 and HP zero.
Native revival takes priority when byte `0x8009DDB7` is 1 and inventory item
47 at `0x800652D7` is present. The native reader and writer take logical slots
1..3; four physical banks rotate underneath them. The last successful native
save/load chooses the slot for this session; actual New Game clears it.

The menu's buffers at pointers `0x800668D8/E0` belong to its stack frame.
Auto reload remembers the successful operation's 0x280-byte header, reserves
fresh stack storage for header and 0x2580-byte payload, and restores pointers
and CPU context afterward. Native reader failure leaves player state unchanged
and resumes ordinary respawn. Successful reads use the native post-load arm
at `0x800189A4..0x80018A04`, then state 254 and the original reverse fade.
Private checks observed cross-floor loading, inventory and equipment restore,
revival priority, missing/changed-card fallback and saved off after restart.

## Color Bars

The separate user-library mod retains red HP and makes MP blue. Power orange
is RGB 245,143,69 (`#F58F45`), Magic cyan RGB 49,160,167 (`#31A0A7`), sampled
from the colored gauge-name underlines on printed page 15 of the official
KF2 manual. Median core-row ink excludes paper and antialiasing pixels.
HUD records at `0x80055C5C`, stride 14, are emitted through `0x8001E480`
at caller RA `0x8001FA18`. Reusing their packet coordinates as flat G4 colors
preserves fill lengths and gold frames; the red original textures cannot
be made cyan by texture multiplication. Native color quantization still applies.

## Gamepad look and enemy turning

Native yaw/pitch defaults are 3, movement sensitivity 1. The previous look
defaults were 1; saved `kf1.analog.turn` and `kf1.analog.pitch` values keep
their values, and neither Classic nor Modern setup replaces them. The values
are direct multipliers, not menu indices: full yaw is 28 units per logic tick
at 1 and 84 at 3, in a 4096-unit revolution. The current native logic rate is
15 Hz, yielding 36.91 versus 110.74 degrees/second. The unchanged seven-unit
acceleration takes four ticks to reach 28 and twelve to reach 84. Native pitch
requests 10 times sensitivity per tick and retains the +/-191 angle clamp.

Creature type definitions start at `0x8006BD98`, stride 152; byte +0x1E is
the angular step. Area 1's twelve slots read 64,64,64,64,32,80,75,75,80,52,0,0.
The angular approach helper is `0x80014A64`. Calls returning to `0x8002ED74`
use the type step during movement; `0x8002ED58` uses floor(3*step/2) while
sliding; `0x800304A0` uses the type step while returning home. Each writes the
creature's yaw at +0x2E toward its target at +0x3A. Creature records start at
`0x8006C4B8`, stride 72; current creature/type pointers are `0x8006E8D4`/D0.

`EnemyTurning` scales only those three callers' step arguments by the effective
configured gamepad yaw sensitivity, bounded 1..4 to match the existing stick
overspeed cap. Disabled analog/look, disabled tank movement, sensitivity <=1
and non-finite values use ratio 1. Default 3 therefore changes the area's
nonzero normal enemy steps from 32..80 to 96..240, retaining each type's
steady angular advantage over the player. Sliding is scaled after its native
adjustment. Zero stays zero; native wraparound and target clamping still run.
Mouse movement, deflection, pitch and optional sustained-stick acceleration do
not change this ratio. Doors/effects and scripted attack spins are excluded;
movement, attack, animation, damage and AI data are not rewritten.

Private-card native checks measured the actual 28/84 player yaw plateaus and
passed 2,255 helper/mode/preservation assertions. A separate process loaded
custom 1.25/2.5 unchanged, and live type-8 creatures used normal/sliding steps
100/150 at custom yaw 1.25, then 240/360 at yaw 3 (original 80/120). Full-down
stick retained pitch clamp 191. This verifies numerical behavior, not combat
feel. Native source commit: `8f3b57ac367609c7a8311214ee6fe3efd18e8336`.

## Extended visible distance

View distance is 0 for the original stencil/fog, or 8..30 cells. The whole
100-by-100 area is already loaded; extending visibility does not load more
collision data. Original DQA=-17600, DQB=20971520 and H=200 reach black near
18333 units (9.17 cells). For an extended distance, retained world depth cue
scales DQA by max(1, cells*2000/18333.333); native fog mode and dynamic dimming
remain active. Map cache identity includes that scale. First-person arms keep
their original cue. Fade remains a separate toggle and does not change cells.

Native model placement subtracts low shorts, wrapping relative positions past
32767. The render scope uses each table's full s32 record/camera coordinates
and adds the rotated missing multiples of 65536 only to the frame-local
placement result at `0x8004DADC`. Gameplay records and GTE registers are not
rewritten. This covers interaction, actor, flipbook, creature and person
submitters even with smoothing disabled. Translucent cached depth is unsigned
u16; world sprites recompute their flat cue from scaled DQA and the exact
read-only H/SZ3 quotient. Max 30 stays below the 65536 depth plane.

Installed-source commit `c4e516a9cc1312fd97302af1a50fa82dd14ad146` visibly
adds farther rooms at 30 versus 15 in matched rendered views. Full-coordinate
placements and far-sprite nonzero visibility were checked in the installed
host. Both settings frontends preserve distance/fade across restart and retain
custom controls and unknown settings.

## Pickup preview and optional feedback

Native pickup inspection `0x800292F8` copies ten u16 glyphs from
`0x80058DC0 + 20*itemId` into its frame-local font descriptor. `0x80058E60`
is entry eight, not the table base. Loose items and container contents share
this preview. Better UI moves only that native name to y=226 through font
`0x80029DE0`, RA `0x80029420`; declining retains the item and disabling restores
native y=36 on the next draw. The preview frame starts at (118,16) and mirrors
the window template's 71-by-104 half in both directions, yielding 142-by-208.
The caption uses that full frame width for centering and centers vertically
in the space below it: two pixels above and below the 12-pixel text cell.
Native font cells advance 14 pixels and are 12 pixels high; their
translated letter pairs retain those metrics. This leaves the caption within
the 240-pixel logical screen. The earlier y=216 overlapped the bottom border.

Hit Feedback brackets actual native damage `0x8002D120` and computes
actual HP lost / definition maximum HP * maximum duration, capped at that
maximum. Default .6 seconds, range 0..5, zero disables; overlapping hits retain
the later expiry. Actor HP is u16 +0x14 and definition max HP is +0x80.
Tint is scoped to actor submission and restores all changed lighting after
submission/unload. Spawn, restore and overlay changes clear timers.

Auto Pick Up All handles semantic operations 64 (loose item) and 65 (gold),
using the accepted native stock-byte increment directly, with item-name glyphs
from the original table sent through NativeNotifications. It does not enter
inspection or synthesize input. Full stacks and a full notification queue keep
the item on the ground. Gold retains its original queue/addition.
Only settled drops within 1000 units (half a map cell) of the player's feet
qualify. Containers 8/9, hidden-height
items, moving drops and full inventory are excluded. These are separate mods
in the user's library, with separate toggles; their payloads do not belong in
Lexeditor source.

Unlocked Pitch is a separate library mod. Native living-player pitch is
normally clamped to +/-191; +/-1024 is a vertical view in the 4096-unit circle.
Its process-only IL hooks widen the mapped stage-A clamp and the Mouse lead
limit. The upper test's 192 constants must be distinguished from SP+0xC0
save/restore offsets in the same routine. PGXP immediate copies must match the
new clamp. Disabling disposes both hooks and returns a living out-of-range view
to the normal cap. The installed host reached both +/-1024 with position/yaw
unchanged; disable restored +/-191 and re-enable worked.

## Interaction records and persistence

Placed objects start at `0x8006EDE0`, stride 44. Type at +0 indexes an eight-byte
definition at `0x8006E8E0`; its first byte is the semantic operation. Real doors
are operations 0, 1 and 2; hinged containers are 8 and item containers are 9.
Cell coordinates are u16 +2/+4; positions are s32 +8/+0xC/+0x10. The render
projection uses their low shorts relative to the camera origin. Do not treat
those shorts as absolute world coordinates.

Only indices 0–159 per floor are persistent placed identities. Slots 160–189
are transient pools. Loot bytes are +0x21..24 for operation 8 and +0x20..23 for
operation 9, with 0xFF empty. Classification uses semantics and remaining loot,
not an object's appearance. Illusory walls are map attribute 0x45 at
`0x8009A748 + 100*z + x`; they never receive a glint. The API also denies any
placed object in such a cell.

The dispatcher is `0x80034DE4`. Selection returns from `0x800315C4` at
RA `0x80035164`; locked chest notification RA is `0x80035320`, locked door RA
`0x80035628`. Successful door action calls return at `0x80035400`, `0x800354F0`
and `0x80035514`. Pair identity comes from the native neighbor search at
RA `0x8003546C`, never proximity alone. The new-player initializer starts at
`0x800151CC`; `0x80015280` is an instruction inside it and cannot be a hook target.
RA `0x80016E7C` distinguishes new-player construction from its respawn caller.

The native save payload is 0x2580 bytes, with four rotating physical banks after
a 0x280-byte header. The card directory filename is exactly the 20 bytes
`BISLPS-00017KF      `, including six trailing spaces. Writer `0x8002B73C` uses
BIOS write `0x800502AC` at RA `0x8002BAB0`; reader `0x8002BEB0` uses BIOS read
`0x8005047C` at RA `0x8002C098`. Both native operations return 1 on success.

Mod metadata lives beside the configured card as `.kf1-extensions.json`.
It never changes card bytes. Each bank is keyed to SHA-256 of the exact payload
captured at the successful transfer; saving also checks the flushed disk payload.
Heap buffers can use mirrored pointers such as `0x807FD8A8` with 2 MiB RAM.
Validate through `MemoryMap.ToPhysical`, the 8 MiB RAM window and the configured
backing-size mask, exactly as `PSMemory` does; a raw 2 MiB address ceiling is wrong.
Bounds are four banks, 32 owners, 4096 bytes per owner and 1 MiB per sidecar.
Disabled owners retain knowledge from the current game's lineage; overwritten
target banks never supply state. New Game clears that lineage.

## Poison and native notifications

The u16 condition mask at `0x800A07AA` uses bit 0 for curse, bit 1 for darkness,
bit 2 (0x4) for poison, and bit 3 for slowed movement. Curse, darkness and poison
timers are `0x800A07C8`, `0x800A07CA` and `0x800A07CC`. Earlier archive notes
called curse poison. The same-disc decomp's `player_status.h`, native status
glyphs and antidote behavior resolve the names.

The periodic poison flash calls `0x8001BAB8` with A0=1 at RA `0x8001A130`;
native preset 5 is green. Ordinary hit flashes return at `0x80019AF8` and must
remain red. Green selection is owned by the independent Better Poison mod.

`0x8001FA44` enqueues native notifications, and `0x8001FAFC` animates them. The
eight-slot queue is at `0x8009506E`, u16 payloads at `0x80095076`, tail/head at
`0x80095086/87`, phase/hold/angle at `0x80095088/89/8A`. This is the bottom
notification system, not the selected inventory item's display. Preset 19 is
GOLD; preset 23 is Poison hole, not a poison status message. Custom lines use
owned valid queue entries and the original menu atlas/sprite routine, preserving
unowned notifications. Menu glyph 0xFF advances a space without drawing.

## Experience

EXP is u32 `0x800A0780`, capped at 99999; next threshold is `0x800A0784`, and
level is u8 `0x800A0788`. The 40-entry threshold table starts at `0x800650B0`,
stride 12, threshold at +8. Values begin 50, 110, 187, 285 and end 69404, 72904.
Beyond the table, thresholds increase by 3500. Level-up `0x80016058` loops and
can award several levels for one gain. Level 48 is the highest normally
reachable level (97404); its next threshold 100904 exceeds the EXP cap.

The XP bar reads these values without writes. Its HUD render event runs before
host ImGui submission and supplies full logical display dimensions. Existing
game-frame snapshots precede ImGui and cannot verify that bar; a temporary
after-host-render backbuffer capture verified the absolute bottom edge.
