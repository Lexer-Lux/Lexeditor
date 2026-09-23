# #319: Identify and restore altered FF8 content

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/319)

## Requirements and decisions

Read the live issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-23 misc-fixes: Lexer chose the restoration policy, stays actionable

Lexer answered the A/B policy question (2026-09-23 comment): for targets 1-4
(Gerogero battle model, Gerogero card-menu art, Armory wall blood, Caraway
armband), find uncensored textures from existing uncensor mods, credit the
authors, and ship them as Lexeditor mod content. For the rest: rename the
nunchaku if the Steam-English source does not already, and remove the Selphie
Scan rotation lock. This replaces the exact-original-only rule: credited
third-party textures are permitted, subject to the normal asset-provenance
and redistribution check (record sources in Credits as used; extract locally
when redistribution is not permitted).

Next agent work, in order:

1. Survey the Qhimm `Final Fantasy VIII Blood uncensor Mods` thread and any
   linked mods for the four target textures; record provenance and
   redistribution rights for each before vendoring anything.
2. Check the Steam-English kernel/menu text for the nunchaku string before
   exposing a rename.
3. Locate the Scan rotation lock and remove it behind a tweak with a test.
4. Implement the four restorations as optional per-mod FFNx overrides with
   strict source hashes and rollback, reusing the validated FS/FI/FL
   extraction and mod-path management. Never redistribute Square's Japanese
   assets and never rewrite base archives in place.

No game install or uncensor-mod archive is available in this session, so no
bytes were vendored and nothing was implemented. Issue stays actionable.

## 2026-09-23 per-game-ff8: Qhimm provenance survey, no vendoring (needs Lexer)

Web survey of the Qhimm `Final Fantasy VIII Blood uncensor Mods` thread
(topic 17469, vavrinko request) and linked releases: the confirmed uncensor
releases found are PSX-lineage (MFS Edit topic 19132, FF8 Improvement Hack
topic 19137) or Remastered-only (McIndus Gerogero Uncensored v1.0, Steam
Remastered only, explicitly out of scope for this issue). No
2013-Steam/old-PC-lineage uncensor mod with confirmed redistribution rights
was found, so no bytes were vendored and no restoration was implemented.
No uncensor research exists in codex/ff8 or games/ff8; the Selphie Scan
rotation lock has no known location in the repo (no scan-runtime or
rotation code beyond Scan text helpers), and the Steam-English kernel/menu
nunchaku string cannot be checked without the game install.

Needs Lexer/game: (1) supply the uncensor-mod archives (or point at the
exact old-PC release) plus redistribution permission per target, or approve
extracting deltas from your own Japanese + Steam installs; (2) game-install
access for the kernel nunchaku-string check; (3) the Scan rotation lock
location (exe address or menu script), or confirmation of what the lock
refers to in game.

## 2026-09-23 impl/ff8-actionables: nunchaku check done, codex noted

New agent-side slice landed: the Steam-English nunchaku-string check.
Decoded `mngrp.bin` uses `nunchaku` (Weapon Monthly 38:14, 38:38,
38:48; test seed 45:2 `Selphie's weapon is the nunchaku`) and no
`shinobou` spelling exists in `mngrp.bin` or `FF8_EN.exe`, so no rename
is exposed. Recorded in new `codex/ff8/altered-content.md` (indexed in
codex/ff8/README.md). Still blocked: uncensor-mod archives plus
per-target redistribution rights (or delta-extraction approval), and
the Scan rotation-lock location. Stays actionable.
