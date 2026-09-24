# #478: Unreal Engine config tool

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/478)

## 2026-09-23 impl/ff8-wave2: Rebirth discovery + Tweaks integration landed

Delivered on this branch: Rebirth Engine.ini location verified against the
installed game (user file live at the candidate path, install ships a
template Engine.ini documenting the same path plus [ConsoleVariables], UE4
crash folders, game-managed GameUserSettings.ini); registry flipped to
config_verified with per-setting effects still unverified (advanced view).
`_documents()` follows the Windows shell Personal folder (redirected
D:\Documents now resolves; fallback unchanged). Rebirth Tweaks page gained
an Engine Config subtab served by new `/api/unreal-config`
status/apply/default/reset/refresh endpoints reusing unreal_config.py (no
per-game editor copy), plus a data-map row and capability. Tests: 22 in
test_unreal_config.py, 4 service/wiring in test_ff7r2_unreal_config.py, 9
verifier checks; live service run discovers D:\ Engine.ini with 15 advanced
settings and zero config. Codex page updated.

Still needs Lexer/game: per-setting in-game effect verification for both
games (normal view is empty until then), release-time builds. Stays
actionable.
