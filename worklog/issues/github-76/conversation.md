# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5311735547 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/76

Created: 2026-09-01T12:19:19Z; updated: 2026-09-04T12:25:07Z

Exact metadata: [source record](sources/issue-5311735547-46ce57da31079e44deb66011eef7ac95203f98557ce227d3ff96f4a52aaed8d9.json).

FF9 already shows a card icon when the player is next to someone they can play Tetra Master with. Make that prompt glow, or otherwise read differently, when the player has not yet beaten that opponent — so a card hunt does not require remembering who is already cleared.

Scope notes:
- FF9 script work (Memoria), not editor work.
- Needs per-opponent "has been beaten" state; check whether the game already tracks it before adding storage.
- Keep the normal prompt appearance for opponents already beaten.

Deferred from a UI session as engine work; not a priority right now.

## issue 5311735547 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/76

Created: 2026-09-01T12:19:19Z; updated: 2026-09-06T13:17:01Z

Exact metadata: [source record](sources/issue-5311735547-d53e262648f7011c6d71bc6ddf1ed292fb8575893bb32e92c869a54703761d25.json).

**Status: Consolidated into Improved Interface (#80).** The request remains: distinguish opponents you have not beaten and restore the normal prompt after victory. It is not a completed standalone feature or a cancelled requirement.
