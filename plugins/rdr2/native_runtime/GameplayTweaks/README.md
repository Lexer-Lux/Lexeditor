# RDR2 GameplayTweaks native source

This directory is the canonical Lexeditor development source for the RDR2
`GameplayTweaks.asi` runtime. The standalone `Lexers-Mod-For-RDR2`
repository is distribution/storage only.

Source migration baseline: `Lexer-Lux/Lexers-Mod-For-RDR2@ccc6c4adcb9262dbd62aeea7901d5864f64680fc`.

## Public-source boundary

This migration intentionally includes source code only. It does **not** import:
- compiled ASI/DLL/EXE files;
- RDR2 game files, extracts, saves, or proprietary data dumps;
- the private `_downloads` research/tool cache or decompiled script corpus;
- generated icon/artwork payloads or other runtime data files.

The source contains comments that cite decompiled-script findings. Those citations
are research provenance; the referenced proprietary script files are not bundled.

The build requires the external RDR2 ScriptHook SDK. Set `RDR2_SDK_ROOT` to a
local SDK directory containing `inc/main.h`, `inc/natives.h`, and
`lib/ScriptHookRDR2.lib`. The SDK is not redistributed here.

MinHook source is vendored under `third_party/minhook` with its upstream
license.

## Build

Use `build.bat` (or `build-dev.bat` for the compile-time development flag).
Build output stays under `.build/`; the build never installs into RDR2 and
never writes to the standalone distribution repository.

## Known migration gap

The #160 handoff references `modules/player_core_rates.cpp`, but that file is
not present in the distribution repository at the migration baseline above.
This migration does not reconstruct missing source from the handoff text.
Recovery/reimplementation and runtime acceptance for #160 therefore remain
actionable after the source tree is centralized.
