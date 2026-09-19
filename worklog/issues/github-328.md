# #328: Correct battle HP bars and XP bars

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/328)

## Requirements and decisions

Latest human test: main-menu XP bars missing; Status bar in Help box. Show XP
below main-menu names, below the shared character level row (including Magic),
and below GF list/detail level rows. Preserve the battle HP/GF HP requirements
on the live issue. Do not claim visual acceptance from native checks.

## Current implementation and evidence

Source 38c9dad replaces wrong save-browser and fixed Status hooks with 13 native
widget call captures. Each capture stores the native viewport and clears after
the frame. GF progress uses the native level function and its XP boundaries.
28fe408 fixes the expired dependency artifact reference in the Windows workflow.

Windows run 34700395103 passed on 2026-09-12. Native widget coordinate checks,
compiled menu capture/projection checks, renderer projection checks, and the
post-battle state/animated-total checks pass locally. Package verification and
installation passed. Installed driver SHA-256:
`6f8b3b67397a9fce8eff7f0258ba8c4fc1bcb4f9702bc31ecfc932bac84fce24`.
XP Bars remains enabled in FFNx.toml. Source package backup is hash-checked under local
Lexeditor helpers/backups/ffnx/xp-widgets-source-20260912.
Installed runtime backup: helpers/backups/ffnx/20260912-085703-176333.

## Next agent work

Human checks are now prepared on the live issue: main-menu active/reserve rows,
Status, Magic, GF list/details, and post-battle page transitions. Live rendering
is not yet accepted. Return a failed check to actionable with the exact screen.
