# Lexeditor FFNx battle repair build

## Artifact and source

- FFNx base: `c056db2783f376a340fcefa6a48cc33618998876`
- Editor build revision: `9a0155df0cd43609690cd8bde4144786915101c5`
- Actions build run: `34035158902`
- Supported private game SHA-256: `064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`
- Identity: `Lexeditor issue 51 shared magic core; base=c056db2783f376a340fcefa6a48cc33618998876; runtime=on; hooks=28`
- Driver SHA-256: `cf237e90a3c0a099c5182e58561e6469951bf2a493bc8a346938aceff2ab0e77`
- Driver size: 38803968 bytes; PE32 x86 DLL
- PDB SHA-256: `1431c8f6f8393ad77c3b834fdd2b9089c1a93898ad4dc69103b079be72d63e92` (build artifact, not installed)
- Complete source patch SHA-256: `9516488302f5eb352ec5e4162bffc6f540fac6150645eb6f040597332219cf79`
- GPL licence SHA-256: `230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`
- Steamworks library unchanged: `abfedd473b3f4a9597bbdc90d20f4b6f696bb2ebb937a03177461df695430ad6`
- Existing matching-base shader set retained: 163 files;
  sorted filename/hash-list SHA-256 `abeb91fc580c5270fb566992e4b16c77e601ea350de46928a8476b1a0e94cd1e`.

The original run compiled and linked successfully, but licence staging used the wrong filename. The archived DLL/PDB and CMake cache were recovered without changing the binary; all linked-artifact and package checks were rerun before publication.

## Changes

Party Switch retires the outgoing model through native event 69 before event
66 loads its replacement. Native saved/kernel names are resolved and measured
before drawing. Cancellation keeps the turn; invalidated reserves reload the
original character; the HUD cache is refreshed after a completed replacement.
Red HP bars use row y+14, not padded glyph dimensions. The independent blue
GF HP bar uses row y+1, fills left-to-right, and uses live charging HP rather
than stale saved HP. Existing XP, targeting, startup and modern-controls code
is retained. Shared Magic + Party Switch remains blocked, not silently enabled.

## Build reproduction

Use the exact FFNx base and its pinned vcpkg submodule. Apply the complete
`ISSUE51_DERIVATIVE_SOURCE.patch`. The build uses MSVC x86 on the
`windows-2025-vs2026` runner, CMake 4.2.0, Ninja, Release, and the
`x86-windows-static` triplet with `VCPKG_BUILD_TYPE release`.
Configure with `FFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON`,
`FFNX_LEXEDITOR_LIVE_CONDITIONS=ON`, and `FFNX_DEPLOY_TO_GAME_DIRS=OFF`,
then run `cmake --build .build --parallel 4`.
The full command sequence is in `.github/workflows/native-dependencies.yml`.
The complete patch restores test/verifier support omitted by the earlier
preparation helper; every candidate patch section was compared unchanged.
No production compilation inputs differ from the reviewed build artifact.
Pinned package files are marked `-text` to prevent checkout newline conversion.

## Validation boundary

The linked artifact verifier passed, including its eleven mutation controls,
and the PE architecture, embedded XML manifest and new runtime markers were
checked before packaging. Repository regressions exercise compiled production
policy/render code and configuration serialization. The private executable
checks exercise native name resolution and model retirement/loading with
resource I/O stubbed. None of these is a live-game or visual acceptance test.
No game executable or private battle capture is distributed or installed by
this packaging command. This report does not claim in-game acceptance.
