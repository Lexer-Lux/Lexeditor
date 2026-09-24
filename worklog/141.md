# #141: Explain and build additional gunsmiths

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/141)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #42 worklog](github-141/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-42.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-22 misc-fixes disposition
Blackwater recognized shop ID is the proposed first example. The interior, merchant, stock, interaction, and persistence setup still needs documenting and proving with the game; no prototype or prepared test exists. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side prototype/experiment
still owed), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 master: stock+merchant documented headlessly, flipped to waiting

Queried the live editable dataset via plugins/rdr2 get_catalog('mine'):
24,706 items; ST_GUNSMITH carries 95 listings, 56 non-advert stock rows
with buy prices (Schofield at 2190 catalog units). Merchant record
(merchant_buyers.json vanillaBuyers ST_GUNSMITH) covers 8 ammo types. Buyer
and catalog keys are by shop TYPE, so the Blackwater location setup
(interior, interaction, persistence) is game-side by nature.

Flipped to waiting with the Blackwater session checklist (shop ID,
interior, merchant, Schofield purchase interaction, save/reload
persistence). Query scripts kept under _scratch (q141_shops.py,
q141_stock.py); no game data modified.
