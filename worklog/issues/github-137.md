# #137: Deliver card drops from smoking premium cigarettes

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/137)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #37 worklog](github-137/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-37.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 loose-card preservation repair

Read live issue and prior verifier before code. The old pack-acquisition watcher armed a three-second window, then removed whichever cigarette-card count increased first. It had no transaction-source identity. A loose-world pickup in that window could therefore be deleted, contrary to the explicit preservation requirement.

Removed that blind inventory deletion. Pack acquisition now reports that native suppression is unavailable rather than deleting unrelated cards. Smoking remains tied to the premium/opened-premium authored consume event442509369 with a rising-edge latch. Chance defaults20%;0/100 are deterministic; unowned cards are preferred until all144 are currently present. No existing card or loose pickup is removed by this module.

`tools/verify_rdr2_smoking_cards.py` executes the production module with controlled inventory/animation inputs. It verifies acquisition/discard do not trigger mod grants, a concurrent loose pickup survives,0% grants nothing,100% grants once per consume edge, opened packs work, a sole missing card is chosen, duplicates become eligible after144, and cigars do not trigger. Four mutations fail. Updated static verifier rejects unattributed deletion rather than requiring it.

Incomplete: Rockstar's original acquisition grant still needs source-attributed suppression before the complete request can be delivered. Main's grant uses reason752097756, but this alone does not establish a safe interception or identify a specific card from inventory polling. Do not relabel as done or repeat a full acceptance test yet. Root owns integration of this preservation repair.

### Acquisition interception boundary

Further source trace: main.c's premium case invokes the common grant function152 recursively with the selected card. The reason752097756 is also used for unrelated weapons, provisions and rewards in the same script; it is not a cigarette transaction identifier. Inside the common grant function, first-time card handling calls func458, which writes COLLECTION through native3EA62E56F386C997 and triggers progress/reward paths. Suppressing only the final inventory native is therefore insufficient: it can leave collection/progress side effects for a card that was never delivered.

A safe suppression target must identify the two grant calls inside the premium-cigarette case before entering the common grant function, retaining all common card grants from loose pickups. Current local runtime has a bundled MinHook library but no established VM program resolver, bytecode call-site patcher, or verified native-handler registration hook. No game-binary address/signature was guessed and no broad native interception was added. Next work needs a build-matched script/VM call-site mechanism with positive and negative transaction fixtures; a reason-only hook and post-hoc removal are rejected.

## Preservation repair delivered, 2026-09-08

Development build passed. Installed ASI and matching release manifest with RDR2 closed; SHA-256 `A1CF1EE032EBEA7A2AAFB566A6299F84ADD9F19FCAED64C01E91AEF2A1782D72`. Small prior ASI rollback retained. No catalog/settings/save changes. Production C++ smoking/preservation tests passed and four mutations were rejected. No game launch. This removes the unsafe deletion only; native pack-grant suppression and full player acceptance remain actionable.
