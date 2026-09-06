# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5347184723 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/86

Created: 2026-09-04T10:51:54Z; updated: 2026-09-04T12:25:16Z

Exact metadata: [source record](sources/issue-5347184723-2b0fdfb078d302e2a9276877d00cbc0e98d9bafebe7eabad6ca0ffcc75405e91.json).

Keep game-research knowledge in Lexeditor instead of copying agent knowledge stores into each mod repository.

Final ownership:

- Each Lexer's Mod repository contains only that mod's distributable source, data, assets, build files, user documentation, licenses, and required attribution.
- Mod repositories do not contain duplicated game-research codices or agent worklogs.
- Lexeditor owns one settled technical codex for every supported game.
- Store game formats, schemas, engine behavior, proven paths, and reusable research under a clear per-game codex path.
- Lexeditor keeps per-attempt implementation evidence in its existing per-issue worklogs.
- When a new game plugin is scaffolded, create and validate its corresponding game codex location automatically.
- Shared Lexeditor implementation documentation remains ordinary project documentation; it does not need a separate Lexeditor codex.
- Migrate existing reusable game research into the appropriate game codex without copying transient attempt history.

Acceptance:

- Every current game plugin has an owned game codex location in Lexeditor.
- Plugin validation detects a missing game codex.
- A newly scaffolded game plugin receives one automatically.
- Lexer's Mod repositories do not receive Lexeditor worklogs or game-research codices.

## issue 5347184723 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/86

Created: 2026-09-04T10:51:54Z; updated: 2026-09-06T12:38:31Z

Exact metadata: [source record](sources/issue-5347184723-052dfac35aa91d5811c6610740193f82671287a473aa40f3ba155589c94f68e3.json).

Each game plugin needs its own technical codex in Lexeditor. New plugins should receive one automatically, with a check for missing documentation. Mod repositories keep distributable mod files, not duplicated research or attempt logs.

**Status: Migration and validation remain unfinished.** No action from you is needed.
