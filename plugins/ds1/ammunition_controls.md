# Later-Game Ammunition

## Scope and use

This is the native implementation candidate for issue #902, not the earlier
read-only probe. It is disabled by default. In a writable Remastered project,
open **Tweaks**, enable **Later-Game Ammunition**, save, and choose **Apply**
with the game closed. **Restore original** removes the patch without changing
the project's saved setting or its parameter archive. No player-side compiler,
DLL, menu archive, probe, or separate injection tool is required.

Only this Windows x64 executable is supported:

- Original SHA-256: `a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`
- Patched SHA-256: `197725ce7cf216e5db1b5c64b464e33377d63a59562dcf19eded5663ea5f0362`
- Original size: 50,286,344 bytes. Patched size: 51,680,256 bytes.

The module rejects all other fingerprints, including other executable tweaks.
It does not silently combine itself with the separate equip-load percentage
candidate or claim compatibility with third-party input/HUD hooks. No merge
of other PRs is included. Parameter mods remain separate.

## Behavior implemented

For the right-hand bow/crossbow, or a two-handed left-hand ranged weapon,
R1 selects primary ammunition and requests the native weak firing action.
R2 selects secondary ammunition and requests that same action immediately.
Logical game inputs are used, not hard-coded XInput buttons, so this does not
replace the game's binding/device layer. An ordinary left-hand weapon and
non-ranged right-hand attacks keep their native paths.

Selection is written to both the saved equipment assembly and the local
actor assembly before the native input consumer runs. The game still owns
projectile spawning, stamina, inventory consumption and reload/draw animations.
A bounded request latch keeps another button from changing the ammunition of
an action already in progress. It uses the native action-inhibit/admission
state, retains the selected slot on release, and does not unlock on an
inventory decrement, which would split an Avelyn burst. Whether every retail
animation transition supplies the expected state still needs in-game testing.

Both existing left/right ammunition widgets are reused, with primary bound to
the right widget and secondary to the left. Each instance has its own item,
icon and quantity cache. Native positions, scaling, drawing, creation and
teardown remain owned by the game. This does not create an overlay or require
a copy of menu.drb. The old active-hand ammo-switch shortcut is suppressed.
Presentation-only precision-mode calls allow both widgets to remain visible;
the obsolete single-ammo widget and switch prompt are hidden, while the native
reticle remains. Reticle children are looked up again before restoring a mask.

## Implementation and executable preparation

`ammunition_native.c` is original freestanding code compiled into a small
native patch, not a custom renderer or driver. C expresses the shot latch,
null/identity guards and widget binding more clearly than hand-maintaining
thousands of machine-code bytes. `ammunition_bridge.S` replaces one complete
CALL after gesture processing and before the native held-duration update.

The emitted 4,392-byte payload has no runtime imports or absolute-pointer
relocations. `tests/ds1/ammunition_build.py --write` rebuilds it with Clang 17
targeting Windows x64. The checked-in JSON contains compressed authored code,
its digest, source hashes, entrypoints and compiler-generated unwind records.
Only development uses a compiler. The application validates all bundled data
before constructing an executable.

The payload begins at RVA 0x319E000, after every original file byte. The final
existing executable/read-only section is extended. A separate, newly declared
128-byte zero-initialized tail of .data at 0x1D0AF80 holds bounded state. Code
is not made writable. The original exception table is preserved verbatim in
a larger sorted table followed by the authored function entries.

Only nine complete CALL/JMP instructions and the documented PE headers change
inside the original file. The signature directory is cleared for this unsigned
candidate, but the original certificate bytes are retained for exact reversal.
`build_hext(True)` exposes the focused native-code fragment; it is explicitly
not independently runnable without the PE/BSS/unwind preparation.

Deployment reuses the shared atomic writer and process check, validates lexical
paths, rejects links/junctions/hardlinks, preserves one original executable
exclusively, and rechecks the live file immediately before replacement.
Windows image-file locking is the final guard against replacing a running game.
Project settings use their own bounded file. The shared `BundledTweak` registry
also exposes the same persistent enable/disable callbacks.

## Verification boundary

The targeted local suite passes 33 tests, including five checks using the private
executable: exact transformation/restoration, mutation boundaries, section and
unwind metadata, modified-output rejection, and real filesystem deployment/
restoration of a temporary copy. The original Library executable is unchanged.

The shipped Windows-x64 machine code passes 67 assertions against fake game
services. These cover routing, hold/release, queued inputs, burst-selection
retention, hand/weapon changes, UI/actor guards, independent icon/count updates,
empty slots, native fallback and reticle-mask restoration. This is actual payload
execution, but it is NOT the retail animation system or an in-game screenshot.

`ds1_ammunition_browser_check.py` uses the real shared editor components and
settings API with a synthetic parameter archive. It covers save/discard,
read-only mode, blocked installation without an executable, narrow presentation,
and preservation of unrelated parameter files. Applied-status presentation in
that test is explicitly simulated.

The draft PR is the current CI record. Retail startup, actual ammo consumption,
bow draw/release, crossbow/Avelyn timing, full native HUD placement, third-party
mod coexistence and online safety are not established by these tests. Keep the
issue open and test the game offline. No game assets or proprietary code dumps
are in the repository.

## Credits and primary references

Native input/HUD entrypoint leads came from lud-berthe's MIT-licensed
Dark Souls Remastered Gyro Aim, `src/Aiming.cpp` at
`d451f3f6403fa4ee24b9fc0868280893fd2e17df`:
https://github.com/lud-berthe/Dark-Souls-Remastered-Gyro-aim-mod

No upstream implementation is copied or bundled. The relevant routines,
assembly layouts, call instructions and quantity addressing were independently
checked against the privately supplied executable.

Microsoft's primary format documentation informed PE/COFF relocations and
x64 unwind records:
https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64

The editor/save/apply shape follows the same-repository DS1 equip-load candidate
at `33fa15b7b3cb6e28ada509b2cd37b21614805db3`, using its shared-control pattern.
Only the ammunition feature is included here. Clang and the test host's C
compiler are development tools, not redistributed player dependencies.
