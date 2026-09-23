# Lexeditor FFNx battle repair build

## Artifact and source

- FFNx base: `c056db2783f376a340fcefa6a48cc33618998876`
- Editor build revision: `f12a03d5e2c8f9bf791b343f6c1817b0f19a650c`
- Actions build run: `35798579648`
- Supported private game SHA-256: `064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`
- Identity: `Lexeditor issue 51 shared magic core; base=c056db2783f376a340fcefa6a48cc33618998876; runtime=on; hooks=28`
- Driver SHA-256: `cf8aa19d233aa6cc69965ac8961759f5aadb7a1670926547e2ca07d052ad9621`
- Driver size: 38859264 bytes; PE32 x86 DLL
- PDB SHA-256: `55487cb04166371b137288548e721cc0ebd768b3f6c251a8f5a768be2fd6dc2c` (build artifact, not installed)
- Complete source patch SHA-256: `537e6e294813b4377912fb5986f77275938578ff356a81e13b966c97f1dcaf0e`
- GPL licence SHA-256: `230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`
- Steamworks library unchanged: `abfedd473b3f4a9597bbdc90d20f4b6f696bb2ebb937a03177461df695430ad6`
- Existing matching-base shader set retained: 163 files;
  sorted filename/hash-list SHA-256 `abeb91fc580c5270fb566992e4b16c77e601ea350de46928a8476b1a0e94cd1e`.



## Changes

Party Switch retires the outgoing model through native event 69 before event
66 loads its replacement. Native saved/kernel names are resolved and measured
before drawing. Cancellation keeps the turn; invalidated reserves reload the
original character; the HUD cache is refreshed after a completed replacement.
HP, GF HP and XP use the measured vanilla two-edge rail profile, with a clear
center, separate anchors, directions and colors.
GF HP requires one junctioned GF and reads live charging HP during a summon.
Menu XP bars follow native character and GF widgets. Active and reserve main
menu rows show progress below LV; character details and GF details show it
below the level row. GF lists show progress below each level. Each capture
keeps its native viewport and clears after drawing. Post-battle XP code remains.
Active main-menu HP also draws below HP X/Y when XP is disabled. Modern Controls
suppresses native camera-left/right input and the overhead-view toggle at their
consumers. Battle camera elevation uses FF8's downward-positive Y axis, so
the floor blocks underground movement and the upper limit allows elevation.
In-game Time uses the native TIME label instead of PLAY.
Better HP Colors adds optional smooth HP-number colour in battle, shared
character panels and active/reserve main-menu rows. Native KO and status
palettes take priority. Interaction Indicators observes the native field target
and adds a CARD cue for Talk scripts that directly contain CARDGAME. Both
settings default off; neither changes input or starts a field interaction.
Party Switch explicitly relinquishes and re-registers the replaced
actor's shared-stock mirror, rather than copying its private record over the
canonical pool. Shared Magic works with the configured stock cap (1–255);
lossless migration refuses overflow. No Magic Consumption hooks only field and
battle spell-cast debits, never the shared Item debit path. Drops After Mug is
a separate guarded one-byte Hext change, retaining Mug-once and reward-once checks.

## Build reproduction

Use the exact FFNx base and its pinned vcpkg submodule. Apply the complete
`ISSUE51_DERIVATIVE_SOURCE.patch`. The build uses MSVC x86 on Windows,
CMake 4.2.0, Ninja, Release, and the
`x86-windows-static` triplet with `VCPKG_BUILD_TYPE release`.
Configure with `FFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON`,
`FFNX_LEXEDITOR_LIVE_CONDITIONS=ON`, and `FFNX_DEPLOY_TO_GAME_DIRS=OFF`,
then run `cmake --build .build --parallel 4`.
The full command sequence is in `.github/workflows/ff8-stock-build.yml`.
The complete patch restores test/verifier support omitted by the earlier
preparation helper; every candidate patch section was compared unchanged.
No production compilation inputs differ from the reviewed build artifact.
Pinned package files are marked `-text` to prevent checkout newline conversion.

## Validation boundary

The linked artifact verifier passed, including its eleven mutation controls,
and the PE architecture, embedded XML manifest and new runtime markers were
checked before packaging. Repository regressions cover all 255 stock caps and three party slots with
repeated swaps, concurrent Draw/cast, canonical save/reload and cancellation.
The linked no-consumption register-ABI hook is executed for all 256 stock values.
Repository regressions also exercise compiled production
policy/render code and configuration serialization. The private executable
checks exercise native name resolution and model retirement/loading with
resource I/O stubbed. None of these is a live-game or visual acceptance test.
No game executable or private battle capture is distributed or installed by
this packaging command. This report does not claim in-game acceptance.
