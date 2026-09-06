# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286460531 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/37

Created: 2026-08-29T12:12:32Z; updated: 2026-09-04T12:24:45Z

Exact metadata: [source record](sources/issue-5286460531-8286b956e6c72613305ee6c04cac30a75b86f3b7f74f1a3d2f87332b5aacb4b0.json).

Save failures must not rely on the narrow command-row status text. Show the failures in one large modal dialog that stays open until the user explicitly closes it. Keep compact status text for routine progress and success messages. Use one shared component across game plugins.

The modal must show a readable error list. Each entry uses `Item: issue`, where Item identifies the affected record or setting. When Lexeditor can resolve that record, Item is a hoverable link that closes the modal and navigates directly to its editor entry.


## issue 5286460531 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/37

Created: 2026-08-29T12:12:32Z; updated: 2026-09-06T13:16:33Z

Exact metadata: [source record](sources/issue-5286460531-dc218de558d53e1fb9926da5549ea8b9ad528344f058ad3e41da873707472a66.json).

**Status: Closed after implementation.** Save failures appear in a readable dialog that requires explicit dismissal. Entries identify the affected item and link to its editor where possible; failed saves retain unsaved changes.

## comment 5462377830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/37#issuecomment-5462377830

Created: 2026-08-29T12:18:55Z; updated: 2026-08-29T12:18:55Z

Exact metadata: [source record](sources/comment-5462377830-b09caa16711ebfee992bb5c03a198c0306ddda9d159e6403833fb2fb61a36c82.json).

Save failures now open one shared blocking modal in FF8, RDR2, RDR, and Warband. It shows the complete wrapping error, keeps the failed edit dirty, and requires the explicit Close button; backdrop clicks and Escape do nothing. The command row now shows only the short Save failed state. Hidden Edge reproduced the upgrade-price rejection and displayed its full message.

## comment 5464934091 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/37#issuecomment-5464934091

Created: 2026-08-29T21:16:55Z; updated: 2026-08-29T21:16:55Z

Exact metadata: [source record](sources/comment-5464934091-7c996ee156036c062cc3d1cc8a9162a2a04b58dcb4c263a1ef87c940a0552d15.json).

Save failures now render as a structured list in the shared blocking modal. Each row uses Item: issue; FF8 rows such as Bismarck are links that close the modal and return to that exact record. The real invalid-price save test preserved the dirty edit, blocked backdrop/Escape dismissal, and required Confirm and Close.
