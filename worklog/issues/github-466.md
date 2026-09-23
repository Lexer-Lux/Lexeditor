# #466: Show item help in a third column on the battle reward screen

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/466)

## 2026-09-22 misc-fixes finding

No battle-results layout code exists in the native tree (the only reward
matches are status-bar code). The three-column rework needs results-screen
drawing-hook research with the game: hook points, available space, wrapping,
mod-edited descriptions, and confirm-once behavior. The acceptance cases from
the issue stand (single, several, long, and modded descriptions). No code
written. Issue stays actionable.
