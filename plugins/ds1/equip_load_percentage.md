# Equip Load Percentage

Experimental, disabled by default. Implements the Remastered-only display tweak
tracked in #872. This is a source candidate, not an in-game-accepted release.

## Use and separation from parameter edits

Select or create a mod, open **Tweaks**, enable **Equip Load Percentage**, and Save.
Save changes only `.lexeditor-ds1-tweaks.json` in that mod. With the game closed,
the tweak's **Apply** button installs the saved choice. Its **Restore original**
button removes the executable patch without altering the saved choice or any
parameter archive. The Information tab's parameter Apply/Restore is separate.

Initial testing must be offline. No multiplayer or anti-cheat safety claim is
made. Unknown executable builds and externally modified files are refused.
Startup, native menu layout, live refresh, locale compatibility and equipment
preview coverage remain unverified in the running game.

The installed backup is `DarkSoulsRemastered.exe.lexeditor-equip-original`.
Only one original is retained, approximately 50.3 MB. Applying grows the
executable by 1,389,304 bytes. Temporary replacement space is released afterward.
Do not remove the original backup while this patch is enabled.

## Exact build

| Property | Value |
| --- | --- |
| Original size | 50,286,344 bytes |
| Original SHA-256 | `a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b` |
| Patched size | 51,675,648 bytes |
| Patched SHA-256 | `a5a68e2ab5439390fff74073a9f3a027d47dfded2e9200c70d36c182bb5c43f9` |
| Preferred image base | `0x140000000` |
| Native hook RVA / file offset | `0x6b3e58` / `0x6b3258` |
| Added code RVA / file offset | `0x319e000` / `0x2ff5800` |

No edition/version claim is inferred from the linker timestamp. Whole-file
fingerprints guard both states. A differing Steam build requires a separately
reviewed profile; no signature-search fallback writes to an unknown file.

## Static trace

The reviewed status update at RVA `0x6b3660` calls the status formatter at
`0x6b3740` and iterates its stat selector. Selector `0x0e` constructs the
combined equip-burden string. The patch replaces that branch's seven-byte
format-string LEA at `0x6b3e58` with a direct jump to authored code.

At this point RSI refers to the menu snapshot obtained through the native menu
data getter. The reviewed code uses `+0x14` and `+0x18` for current and maximum
load, and `+0x40` and `+0x44` for nonnegative comparison-preview overrides.
These associations are static evidence, not a report of runtime observation.

The island keeps R8/R9, the already formatted current/max strings, unchanged.
It computes `100 * current / maximum` as a double, choosing the same nonnegative
preview overrides. Negative zero in an override is normalized to zero.
Invalid selected values or a nonpositive maximum fall back to the original
format without dividing.

The extra variadic double goes at `[rsp+0x20]`. RDX becomes the authored
UTF-16 format `%s/%s (%.1f%%)`. A direct jump resumes at RVA `0x6b3e5f`, before
the existing call to the game's formatter at `0x0c5c00`. The game retains string
allocation, formatting, colouring and drawing. No new renderer, DLL, timer,
save-file write, stat write, roll threshold or gameplay calculation is added.
One-decimal display rounding is cosmetic and can round across a threshold.

This location is in the shared status-display path. Coverage of both requested
screens and comparison behavior must still be confirmed in-game; do not turn
this static trace into a claim that both screens were observed working.

## Executable preparation and unwind handling

The apparent tail padding in this executable was **not** free: a full byte check
rejected it. No existing code cave is used. The last existing executable,
read-only section is extended past all original file bytes for the island and
a complete replacement exception table. No writable-executable section is added.

Every original function-table entry is copied locally, unchanged, into the
new sorted table. A final entry covers the island and points to chained unwind
metadata referencing the original function's entry
`(0x6b3740, 0x6b3f38, 0x182bffc)`. This is a mid-function jump, not a leaf call:
without that chain, Windows unwinding could treat the parent stack frame as a
return address. The island changes no nonvolatile registers or RSP.

Section sizes, image size and exception-directory headers are updated. The PE
checksum and security-directory reference are cleared because modification
invalidates the original signature. Original certificate bytes are retained
in the preserved prefix. Whether the game/bootstrap accepts the prepared image
is an outstanding native startup test.

`build_hext(True)` emits the focused native-code Hext fragment. It is NOT a
standalone live-process patch: this plugin's file transformation prepares the
necessary PE space and exception metadata first. All branches are PC-relative.
There is no custom native runtime. Disabling validates the patched hash, restores
the exact original header/instruction bytes, truncates the extension and verifies
the original full-file hash.

The code allocates no recurring cache or log. File deployment rejects symlink,
junction and hard-linked protected paths; it verifies the backup and live bytes
before mutation, checks for a running game and uses the shared atomic writer.

## Reproducible checks

Run the focused suite:

```sh
python -m unittest discover -s tests/ds1 -p test_ds1_equip_load_percentage.py -v
```

An optional private local check takes the unmodified executable from
`LEXEDITOR_DS1_EXE`. This input is never uploaded by tests or committed.
Without it, the real-build roundtrip test is explicitly skipped.

Synthetic tests exercise idempotence, unknown-build rejection, preservation of
all original bytes outside declared writes, direct branches, exception metadata,
settings permissions, save/apply separation, bounded backups, conflicts,
restoration, links and interrupted atomic replacement.

On x86-64 Linux with GNU binutils, the suite also assembles the authored source
and compares the exact template bytes. An isolated native shim executes those
bytes for known cases and 200 deterministic random float32 input pairs, checking
the result, arguments, nonvolatile registers, stack pointer and immutable
snapshot. This does not execute the game's formatter or Windows loader. That
harness is explicitly skipped on other platforms.

`ds1_tweaks_browser_check.py` uses the real shared controls and synthetic
parameter archive to test the settings API, save/discard behavior, unsupported
build state, narrow rendering and read-only controls. Any applied state shown
by that test is explicitly simulated, not a native-game result.

## Remaining acceptance

Keep this experimental and #872 actionable pending these results:

- Windows startup with this exact build after Apply; no bootstrap failure.
- Equipment AND Status screens show the added percentage beside unchanged
  current/max numbers, with no clipping at supported resolutions and scales.
- Equip/unequip weapons, armor and capacity-changing rings; compare candidate
  equipment, cancel it, and reopen menus. Both numbers and percentage must agree.
- Check zero load, overloaded load and values around roll breakpoints. The
  patch must change only text, including after ring effects and stat changes.
- Disable via a saved unchecked setting plus Apply, or Restore original.
  Verify ordinary native presentation returns and the original hash is restored.
- Test native locales and observe any text-width/font problems. Do not claim
  online safety, generalized build support or visual acceptance from unit tests.

## Primary technical references

- Microsoft, x64 exception handling, including chained unwind information:
  https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64
- Microsoft, PE format and exception-table layout:
  https://learn.microsoft.com/en-us/windows/win32/debug/pe-format

The native trace was derived from the privately supplied Remastered executable.
PTDE pointers and the previously researched PTDE mod are not used in this patch.
No game executable, copied game table or proprietary disassembly is distributed.
