# Battle HUD and reserve switching

## Verified executable

Steam English `FF8_EN.exe`, SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.
The addresses below are specific to this executable. Source: disassembly and
execution checks in `tools/verify_ff8_native_battle_regressions.py`.
Keep the game executable private; pass its local path through `--exe`.

## Model ownership

Battle model records start at `0x1D972C0`, stride `0x9C`. Native event 66
calls loader `0x502670`, which does not start while model flag bit 0 is set.
Replacing a living character without retiring its model leaves this loader
waiting indefinitely. Event 69 dispatches `0x502ED0` and effect `0x50C5F0`;
these perform the native removal and resource release. Preserve live HP,
spell stock and statuses before retirement, which marks the old actor KO.
Only queue the replacement after the model ownership flag clears. Refresh
the cached HUD with `0x4B18C0` after loading, not just computed actor stats.

The presentation-event allocator `0x503270` scans twelve-byte records using
record byte `+1` as the allocation flag. The descriptor at `0x1D96D68` stores
the pool at `+8` and capacity at `+12`. Native event 0A passes its four-byte
payload to the callback. Guard callback generations across mode changes.

## Names and bars

Resolve selector names with `0x47EB50`; saved Squall/Rinoa names and kernel
names use different paths. `0x4A7250` draws ordinary encoded glyph strings;
it stops on the old 03/ID control sequence without drawing a name.
Measure these strings with `0x4B1850`, using the same nibble-width table.

The native HUD row has x/y at `+8/+0xA`, max/current HP at `+0x1C/+0x1E`,
and actor slot at `+0x48`. Rows are 15 native pixels high, names start at
row y+2. Anchor the red HP line at y+14 and blue GF HP line at y+1, then
apply the captured native viewport and FFNx output transform. Glyph atlas
padding is not an appropriate vertical anchor.

Junctioned GF IDs come from the character's saved bitmask. Computed GF max
HP is at `0x1CFF61A + gf*12`. During summoning, the actor computed record
uses flag bit 0 at `+0x1C`, GF ID+0x40 at `+0x1D`, and live current/max HP
at `+0x18/+0x1A`. Use those live values for the summoning GF instead of
its saved HP. The overlay aggregates current/max for multiple junctioned GFs.

## Test boundary

Native execution tests exercise these instructions with resource I/O stubbed.
`verify_ff8_native_compiled.py` executes production C++ with instrumented
native I/O; `verify_ff8_gf_bar_settings.py` checks independent per-mod settings.
Neither establishes live visual acceptance. The combined FFNx derivative
uses base `c056db2783f376a340fcefa6a48cc33618998876` and the preparation helper
`tools/prepare_ff8_native_build.py`. A source change does not update the
packaged driver or authorize changing its pinned artifact hashes.
