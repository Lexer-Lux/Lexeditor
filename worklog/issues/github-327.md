# #327: Signal Flare and Modern Controls

Canonical request: https://github.com/Lexer-Lux/Lexeditor/issues/327
Status: actionable. The full feature is not delivered.

## Requirements and current decisions

Use the new item to trigger a random encounter appropriate to the current
location and show its remaining count through a fuel-style notice. Square/the
PC equivalent requires Modern Controls. Vehicle forward/reverse move to analog
triggers with keyboard equivalents. Do not replace an existing item.

On 2026-09-08, Lexer named the item **Signal Flare**, to distinguish it from the
Flare spell, and asked whether shops have free slots. Runtime text, source
messages and tests use Signal Flare; internal `flare_*` names remain.

No stock shop has a free slot. The private baseline `shop.bin` is 640 bytes:
20 shops x 16 ID/rarity pairs, all 320 IDs populated (no 0 or 255). This includes
Balamb, Dollet, Timber, Deling City, Winhill, FH, Esthar Cloud's Shop, Timber and
Esthar pet shops, Esthar Book Store, and Esthar Shop!!!. Unused/Laguna tables are
also full; hidden/rare goods still occupy real slots. Baseline SHA-256:
`2351fedf7eab6fcbb5823a344a727e29096d3237543b322c8f9372e52a847e82`.

Lexer then selected **all shops** and asked for a fairly cheap price. The new
record costs **200 Gil**, with normal 100 Gil resale. Baseline price.bin confirms
Potion 100 Gil, Hi-Potion and Phoenix Down 500 Gil, and Tent 1,000 Gil; native
records store tens of Gil. All 20 shop lists default to the extra listing.
There is no remaining acquisition design question.

## Delivered slice: proportional vehicle controls

`vehicle_drive.h` keeps partial analog pull proportional even when its digital
trigger alias is also set. Keyboard-only input still gives full forward/reverse.
The maintained patcher includes the required header.

An explicitly LOCAL FFNx candidate is installed at
`D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/AF3DN.P`, SHA-256:
`8098b647d4f0ba1e61396f42da8329cda1d014ee5313503016aa77063007848e`.
FF8/launcher were closed. FFNx.toml stayed byte-identical and Modern Controls
was already enabled. The DLL is based on FFNx
`c056db2783f376a340fcefa6a48cc33618998876` plus the recorded dirty local source
patch. It is not an Actions artifact or official release.

`out/ff8-native-candidate/` contains the source patch, input hashes, BUILD.txt,
PDB, test instructions and one rollback under `local-install/`. Original DLL:
`655ca256e95bfc48e6d5a8d1e969ca75276f278d6d830d9d573142eee607a473`.
Rollback: `.venv/Scripts/python.exe -m games.ff8.local_native_candidate rollback out/ff8-native-candidate`.
The installer checks the supported EXE, explicit DLL hash, PE exports/XML,
provenance and closed-game state; it preserves settings and refuses unrelated
later DLL replacements. Official package trust policy is unchanged.

The candidate passed linked-runtime mutation guards, Modern Controls markers,
Reptile ATB checks and actual linked no-consumption hook emulation. Proportional
vehicle behavior still needs a game test; no vehicle-ready save was supplied.
**This installed DLL does not include the Signal Flare work below.**

## Signal Flare source implementation (not linked or installed)

- **World selector:** `flare_encounter.h` and `lexeditor_ff8_flare.cpp` use the
  stock selector at `0x541C80`. Region/ground matching and weighted formation
  choice stay native. Temporary movement is restored; failed requests restore
  counters/output. Native vehicle, encounter-disable and terrain guards remain.
  Attempts are bounded to 256. Invocation belongs at the existing FFNx world
  battle gate so battle transition and music retain their owner.
- **Inventory:** 198 ID/quantity pairs at `0x01CFE79C`, not a 198-ID definition
  table. Native add `0x47ED00` accepts byte ID 199 in a free slot and does nothing
  when full. Normalization `0x4C3150` keeps it. Successful use consumes one and
  returns the count; missing/corrupt/duplicate stacks and failed selection cause
  no debit. The native entry accepts only the allocated new ID 199.
- **Definition/text:** `flare_item.h` contains only new, source-owned data.
  Name/description hooks at `0x47EA30`/`0x47EA90` keep all stock lookups. The fixed
  kernel tables are not enlarged. Unknown IDs return empty text. Three mitem
  loader calls use game-owned 1 KB buffers, preserve the 796-byte stock prefix,
  and give unused byte IDs inert records. Already-expanded files are collisions.
- **Menu dispatch:** the guarded hook at `0x4F8A2F` retains stock instructions.
  Unknown IDs refuse. Signal Flare calls a bound request owner; acceptance uses
  stock item-pane close states `0x70/0x71`, refusal returns to state 4 with native
  error feedback. The use flag is exposed only if an owner binds before metadata
  load. Actual executable tests show these close states return to the main menu;
  the world-return owner is still required. No request owner is bound yet.
- **Shop safety:** the stock initializer reads 200 price rows from a 199-record
  file. A game-owned wrapper adds the defined 200 Gil Signal Flare price record.
  Buy/sell guards refuse ID 199+ before Gil/staged stock writes. This is temporary
  refusal, not final Signal Flare pricing or availability.
- **Extra listing:** `flare_shop.h` and `lexeditor_ff8_flare_shop.cpp` redirect
  all 28 known buy-list ID/quantity/end operands to a bounded 198-row transient
  buffer. Both entry paths refresh it after native filtering. Selected shops
  can append one listing without changing the saved 16-slot shop records. A
  full list gets a third page; other shops keep two pages and clear prior extras.
  All 20 shops default to the added listing (100-item quantity cap), with three
  eight-row pages at maximum: 16 stock goods plus Signal Flare. Compiled x86
  refresh tests cover all 20 defaults. Purchase readiness remains guarded until
  full use/save integration. Native cursor/renderer acceptance remains open.

All installers remain disconnected from startup until the full owner is ready.
No stock Flare Stone (27), Fuel (162), shop entry, save, or game data was replaced.

## Evidence and next work

Latest FF8 subset: 84 tests and 110 subtests pass. Focused checks execute the
production C++ policies, loader, menu handler and compiled x86 bridges; they cover
512 buy/sell register cases, menu register/stack preservation, 100 loader cycles,
all 398 stock name/description lookups, collision/capacity rules, shop page/reset
behavior, and actual native lookup of a seventeenth transient listing. The
supported private EXE supplies native selector, inventory, menu cleanup and
operand evidence; rendering/audio side calls are stubbed. This is not visual or
gameplay acceptance.

Four Signal Flare translation units compile with MSVC x86 in the existing
`_scratch/issue51-ffnx-build-c056db2` generated build tree. No dependency rebuild,
new DLL link, game launch or new installation occurred. Test fixtures use cleaned
temporary directories. Keep installed candidate provenance unchanged.

Next agent work:
- Connect request ownership, main-menu exit, world battle gate and count notice.
- Connect both world and field selectors to their native battle gates.
- Retain the native save round-trip regression; gameplay save/reload remains untested.
- Finish shop cursor/render/transaction integration with all shops and 200 Gil.
- Bind acquisition and startup only when all dependent paths are ready, then
  build a truthful local candidate and prepare a reproducible gameplay test.

## Native save path proof (current)

`tests/test_ff8_flare_encounter.py` now executes the actual supported EXE save
formatter `0x4E2EF0`, checksum `0x500310`, compressor `0x40FE1D`, decoder
`0x40F852`, and file-load helper `0x4C6D60` with synthetic buffers. It preserves
ID 199 / quantity 37 in the last of 198 inventory slots through the 8 KiB save
block, compressed bytes, and restored savemap. Only OS file I/O, allocation and
compressor diagnostic printf are stubbed. Both saved checksum copies match.
No game process or user save was touched. Focused regression passes.

Supported savemap base is `0x1CFDC58`, recovered from intro `0x470319`, and
inventory offset is `0xB44` (not the earlier inferred alternate-layout `0xB54`).
No save expansion is needed. `create_save_file_sub_4C6E50` converts/compresses an
existing file; it is not the live formatter. Native load copies 0x1400 bytes from
the decompressed block's 0x180 offset. Whole gameplay load remains untested.

## Menu exit and field selection (source only)

`lexeditor_ff8_flare_menu.cpp` now owns the requested root-menu exit. It waits
for child cleanup (root state 7, stack depth 1), then invokes stock states 21/22.
Those states commit the selected party, fade for 16 frames, remove the root
context, and return depth to zero. It reports readiness only afterward and does
not read the context after native code can free it. Requests cannot stack; reset
and disabled-feature paths clear pending work. The guarded registration patch is
not bound to startup. `tests/test_ff8_flare_item.py` tests the compiled production
owner; `test_ff8_flare_encounter.py` executes the native root states and verifies
party commit, fade and one cleanup. Rendering/context allocation are stubbed.

The field backend now uses the actual current-map four-formation table and
native weighted RNG. It keeps movie/activity and transition guards, and refuses
maps with zero encounter rate. `request_field` temporarily raises step/danger;
failed attempts restore counters and RNG indices. Native return EAX is undefined
on some refusal branches, so success is read from native battle-transition state
3 and flag 1, not that return value. Both field/world item use share the validated
inventory debit and remaining-count return. Native emulator tests verify local
formations and encounter-disable behavior; portable policy tests verify restore.

All four translation units compiled with the existing MSVC x86 build cache.
These menu/field changes remain source/object only, not in the installed DLL.
The full request owner must still bind menu admission, exit readiness, both
native battle gates and count feedback; startup and purchase remain guarded.
