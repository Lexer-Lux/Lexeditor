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
