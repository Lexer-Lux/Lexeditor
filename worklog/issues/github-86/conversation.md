# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## verbatim-user-request chat-2026-09-06-preservation-request — Lexer

Source: not recorded

Created: None; updated: None

Exact metadata: [source record](sources/chat-2026-09-06-preservation-request.json).

Oh my god.
So, half of waiting tasks are just "no context was given, I have no clue what to do". So every time I give you an issue to create, I go into ridiculous, painstaking levels of detail. I'll write like paragraphs and paragraphs of shit, and you just intentionally throw that all out away and then complain that I didn't give you enough info? Like... How do I stop you from ever doing that again? And on that note, you have the internal Worklog.txt for the issues to store all the issues there internally, so you can keep the GitHub nice and clean and laconic. And you should be deleting all the comments and stuff as well on every issue. So if you need to have info from those, you need to migrate from those. Again, that goes in there. You know, but since we're running lots of stuff in parallel, maybe every issue should have its own work log file. I don't know.

And also related to that is the codex. You need to grab the codex, separate one we have for, like, every Lexers mod, every game, and centralize that onto Lex editor. Each game has its own codex.&#x20;

Another issue is that since we're running all this stuff in parallel, um, you know, maybe we'd have to do all that now and then when all that's done running, we'll merge it and then you can just do that bit again with whatever new stuff they might have added to their workload or Codex. I don't know.

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
