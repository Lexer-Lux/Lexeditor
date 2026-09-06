# GitHub #20 - Dev Mode

## Requirement

The issue requested a compile-time flag that enables or disables
development-only features.

## Implementation

- Added `GameplayTweaks/development_build.h`. It defines
  `GAMEPLAYTWEAKS_DEV_MODE` as `0` unless the compiler explicitly supplies a
  value and rejects values other than `0` or `1`.
- Added `GameplayTweaks/build-dev.bat`. It injects
  `/DGAMEPLAYTWEAKS_DEV_MODE=1` through MSVC's `CL` environment variable and
  delegates to the authoritative `build.bat`, avoiding a duplicate compile or
  link command that could drift.
- A normal `build.bat` invocation therefore remains a release build. An
  explicit `build-dev.bat` invocation is a development build. Both still
  produce the single `GameplayTweaks.asi` artifact.

## Integration handoff

The integration-owned `script.cpp` must include `development_build.h` and gate
the existing development controls at config-load time. The known controls are
`Prone.DevelopmentTrace`, `Climbing.DevelopmentTrace`,
`CombatRoll.DevelopmentTrace`, and `SpentCasings.DebugMarker`. Each resulting
runtime boolean should be false unless
`GameplayTweaksBuild::Development` is true; the INI setting can then decide the
value only inside a development build.

This config-load gate is preferable to changing only each default: a release
build must ignore a stale installed INI whose development switch is still `1`.

## Static checks

- Confirmed the default macro is `0`.
- Confirmed the development wrapper supplies exactly
  `/DGAMEPLAYTWEAKS_DEV_MODE=1` and calls the authoritative `build.bat`.
- Confirmed the header rejects non-boolean compile-time values.

The feature agent did not compile, install, edit GitHub state, or touch the
integration-owned dispatcher/build entrypoint.

## Runtime toggle follow-up

The requested development-build runtime switch is now integrated. A build made
with `build-dev.bat` starts with developer mode enabled. Pressing the physical
backtick/tilde key (`VK_OEM_3`) toggles it for the current session and posts
`Developer mode enabled` or `Developer mode disabled` through the normal feed.

Toggling reloads the INI-backed development settings. When off, it disables
collectible/bottle probes, prone/climbing/combat-roll/horse-needs traces, spent
casing debug markers, the F2 collectible correction key, and the campsite
authoring key. A normal release build compiles the key handler out and keeps all
development-only features disabled regardless of INI values. Toggle events are
also appended to `GameplayTweaks.dev-mode.log`.

Runtime acceptance requires installing a development build, then pressing
backtick/tilde twice and confirming both feed messages and `enabled=0` followed
by `enabled=1` in the log.

## 2026-08-11 returned-test audit: release lost prone

Lexer reported that the release ASI did not permit normal prone entry. This
invalidated the assumption that a release artifact was a safe gameplay
baseline. The failure class from `fuckups.txt` was a disconnected guardrail:
the existing verifier checked the macro and toggle text but did not prove that
normal gameplay dispatch was identical across development and release builds.

Current source evidence is narrower than the failed artifact. `Prone.Enabled`
is read without a development gate, and `updateProne(...)` is called outside
the development-only block. Only `Prone.DevelopmentTrace` depends on runtime
development mode. The current development consumers are limited to diagnostic
settings, camera and fortification editors, developer-only settings rows, the
F2 collectible correction key, and the tilde authoring switch.

The repair compiles the tilde handler only in a development build and adds a
static parity contract that rejects any development gate in the movement
module or the prone dispatcher. This does not prove the returned release
artifact's exact historical source or prove prone in-game. Runtime acceptance
now requires the same prone entry test in both artifacts, plus confirmation
that release omits authoring controls while retaining gameplay features.
