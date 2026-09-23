# #498: Separate the menu volume control into SFX and Music

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/498)

## 2026-09-22 misc-fixes finding

No volume or audio-path code exists in the FF8 plugin (only unrelated
init_data.py matches). Separate SFX and Music sliders need menu plus FFNx
audio-path research with the game first: which backend owns each category,
where the single Sound slider writes, and persistence across restart. No code
written. Issue stays actionable.
