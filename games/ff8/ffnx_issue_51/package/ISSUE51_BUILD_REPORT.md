# Lexeditor FFNx battle repair build

## Artifact and source

- FFNx base: `c056db2783f376a340fcefa6a48cc33618998876`
- Editor build revision: `e7a3e40fb4c32d6fde02c096aae822a683ef6e77`
- Actions build run: `35159257215`
- Supported private game SHA-256: `064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`
- Identity: `Lexeditor issue 51 shared magic core; base=c056db2783f376a340fcefa6a48cc33618998876; runtime=on; hooks=28`
- Driver SHA-256: `b38a52a2582dc250caef68b15e41f6d8daa153098b0bb1bddbd00cec51cfc4f3`
- Driver size: 38850560 bytes; PE32 x86 DLL
- PDB SHA-256: `bb0a063894233821dbc5997e02d4cadd7c2b688c806f3d34048177b9b1bb9007` (build artifact, not installed)
- Complete source patch SHA-256: `27de2b4685ce1ad4359954d8293a18e5fb14f08db971d8ecbcea4f11d961fd83`
- GPL licence SHA-256: `230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`
- Steamworks library unchanged: `abfedd473b3f4a9597bbdc90d20f4b6f696bb2ebb937a03177461df695430ad6`
- Existing matching-base shader set retained: 163 files;
  sorted filename/hash-list SHA-256 `abeb91fc580c5270fb566992e4b16c77e601ea350de46928a8476b1a0e94cd1e`.



## Changes

Party Switch retires the outgoing model through native event 69 before event
66 loads its replacement. Native saved/kernel names are resolved and measured
before drawing. Cancellation keeps the turn; invalidated reserves reload the
original character; the HUD cache is refreshed after a completed replacement.
Every bar is FF8's menu gauge: a one-pixel colour line on a two-pixel black
track. Battle HP spans a four-digit field under the drawn HP digits; GF HP
spans the name above it; both fill by current/max. Menu XP bars now show their
fill. GF HP requires one junctioned GF and reads live charging HP during a summon.
Modern Controls: the camera's vertical axis is no longer inverted; in battle,
RT or the left mouse button is R1 (trigger, Shot), LT or the right mouse button
holds L2+R2 (flee), and B or Backspace ends Shot. The camera speed setting is
declared in the derivative config.
Menu XP bars follow native character and GF widgets. Active and reserve main
menu rows show progress below names; character details and GF details show it
below the level row. GF lists show progress below each level. Each capture
keeps its native viewport and clears after drawing. Post-battle XP code remains.
Party Switch explicitly relinquishes and re-registers the replaced
actor's shared-stock mirror, rather than copying its private record over the
canonical pool. Shared Magic works with the configured stock cap (1–255);
lossless migration refuses overflow. No Magic Consumption hooks only field and
battle spell-cast debits, never the shared Item debit path. Drops After Mug is
a separate guarded one-byte Hext change, retaining Mug-once and reward-once checks.

## Build reproduction

Use the exact FFNx base and its pinned vcpkg submodule. Apply the complete
`ISSUE51_DERIVATIVE_SOURCE.patch`. The build uses MSVC x86 on the
`windows-2025-vs2026` runner, CMake 4.2.0, Ninja, Release, and the
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
