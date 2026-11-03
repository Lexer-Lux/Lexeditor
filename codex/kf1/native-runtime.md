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
This archive has no Remaster Editor. F2 belongs to the optional Debug Tools mod.

Retail has no sprint stamina pool or drain. Held run scales collision movement
by two before collision resolution. Lexer chose to use weapon power for Better
Sprint, so its actual vanilla drain default is zero. Current weapon power is
u16 at `0x800A0798`, full at 5000, and is also used by attacks. Magic charge is
separate at `0x800A079C`; MP is at `0x800A0796`. The native charge recovery remains
active. A sprint policy receives actual displacement after the player stage and
the logic tick duration, independent of rendering frequency.

## Interactions and persistence

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
