# Worklog: Github 48

## GitHub #48 immediate drowning at zero swimming Stamina — 2026-08-05

Added the death transition to the existing outer-bar controller. While the
player ped is actively swimming, an outer Stamina value at or below 0.01 now
sets ped Health to zero immediately. The check excludes lost-control states,
death, shallow-water wading, horses and ordinary on-foot exhaustion. It does
not read or spend the Stamina Core.

GameplayTweaks built successfully with the two pre-existing C4838 warnings and
was installed while the game was closed. Source and installed ASI SHA-256:
`D1986258D0B8C36F7025154EB51AC4D326049FA0B407B6E3EBF4B03C1AFED17B`.
Runtime behavior remains unverified pending Lexer's swimming-exhaustion check.

