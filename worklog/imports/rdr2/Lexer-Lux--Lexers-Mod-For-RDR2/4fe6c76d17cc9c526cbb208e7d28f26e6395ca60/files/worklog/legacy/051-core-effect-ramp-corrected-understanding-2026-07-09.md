# Worklog: 051 Core Effect Ramp Corrected Understanding 2026 07 09

## CORE-EFFECT RAMP — corrected understanding (2026-07-09)

- **Lexer never wanted a custom vignette.** The feature is: ramp the intensity
  of the VANILLA low-core/low-health screen effect with emptiness (instead of it
  snapping on at empty). "It should be like the base game effect, which is not a
  vignette at all." So the v3 custom-sprite/ytd approach was WRONG — and the
  whole OpenIV/ytd/CodeWalker tooling wall below is IRRELEVANT to this feature.
- **CoreVignetteRamp v4** (installed 2026-07-09) reverts to the v1/v2 approach:
  drive the vanilla animpostfx effect by name via ANIMPOSTFX_SET_STRENGTH,
  strength = f(emptiness). Effect name + Source(core/bar) + KeepAlive(play/timed)
  are all ini-configurable and hot-reload, so Lexer picks the exact base-game
  effect live. Candidate effect names: PlayerHealthPoor, PlayerHealthLow,
  PlayerHealthCrackpot, PlayerRPGEmptyCore{Health,Stamina,DeadEye}, PlayerRPGCore,
  DeadEyeEmpty. The old "pulse in/out" was re-trigger flicker (try KeepAlive=timed)
  vs. an effect's inherent throb (pick a steadier effect). corevignette.png /
  sprite code / stream ytd are all abandoned.

