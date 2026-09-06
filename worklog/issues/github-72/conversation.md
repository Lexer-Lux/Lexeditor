# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5295171951 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/72

Created: 2026-08-31T00:22:00Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5295171951-a454a7dbc7d5b47afea36eaa7560dccb182217c10398d77a4c35000d58f59abb.json).

Add a shared semantic sound contract for confirm, back, move, launch, exit, and save. Plugins can privately extract matching UI sounds from an installed game and report per-slot coverage in the game Info page while Developer Mode is active. Add a global Sound setting, enabled by default. FF8 and both FF7 products are the first adopters. Source sound IDs must be proven; semantic Lexeditor names must not be presented as game-internal filenames.

## issue 5295171951 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/72

Created: 2026-08-31T00:22:00Z; updated: 2026-09-06T13:06:58Z

Exact metadata: [source record](sources/issue-5295171951-f5cb7bde3815b6be4610bb0502bf53566dbf96146b933ae7d53991492b407149.json).

**Status: Sound playback is implemented; the choices need your listening check.** FF8 has all six sound roles. FF7’s Launch sound remains unavailable rather than using a guessed substitute.

- [ ] Restart Lexeditor with Sound on. In FF8 and FF7, move selection, confirm, go back and save a disposable edit. Check the sounds match the actions and are not doubled.
- [ ] Turn Sound off and repeat: the editor should be silent. Restore your preference.
- [ ] Report the game/action and any missing, unsuitable or repeated sound; do not count FF7 Launch as a new failure.

## comment 5472349138 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/72#issuecomment-5472349138

Created: 2026-08-31T00:47:56Z; updated: 2026-08-31T00:47:56Z

Exact metadata: [source record](sources/comment-5472349138-0649fb1d456e040725d7e0a7eeefd4d2acf065b1c66e9f22c79d1b3203562561.json).

Added shared Confirm, Back, Move, Launch, Exit, and Save sound slots, the default-on global Sound setting, private cached extraction, and a Developer Mode coverage table. FF8 maps records 1, 9, 29, and 37 across the six roles. FF7 maps 1, 2, and 4; Launch remains unavailable because no game-start record was proved. Extraction converts the game ADPCM records to browser-safe PCM, and Edge decoded every FF8 slot plus all five mapped FF7 slots. Please confirm the sound choices by ear.
