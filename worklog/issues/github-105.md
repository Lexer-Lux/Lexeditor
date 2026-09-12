# #105: Finish manual control of the belt lantern

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/105)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #5 worklog](github-105/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-5.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 manual-state and crouch repair

Read live #105 and #348, existing corrections and focused verifiers. #348 routes behavior to #105 and supplies no later stow/off decision. Current code already sampled crouch, capped brightness at0.8 and rejected crouched radial selections, so the live summary saying no crouch code is stale. Actual defect: later code deleted the unlit prop and excluded crouch from effectiveLit, despite the retrieved explicit persistent-unlit/forced-dim policy. Its diagnostic already reported crouch OR saved state, which did not match its draw decision.

Player prop now persists while eligible/unmounted regardless of saved light state. Effective light is crouch OR savedLit, with crouch brightness min(configured,0.8). Standing restores saved light/brightness automatically because crouch never changes the saved latch. Existing mission/death/swim/ragdoll gates, mounted suppression, physical attachment and saddle light are unchanged. Crouched radial selection remains functionally rejected; genuine greyed provider feedback remains unresolved.

`tools/verify_rdr2_lantern_crouch.py` executes actual prop/light branch: off→crouch→stand, on→crouch→stand, low/zero brightness, persistent unlit prop and mounted suppression pass; three mutations fail. Existing light-controls202 passes16 mutations and horse203 passes4. Belt5's crouch/attachment/source contracts pass; its pre-existing attachment-INI default check still fails for the user's selected non-default anchor and was not used to rewrite their settings.

Root owns build/install. Remaining acceptance is rendered persistent prop, crouch dim/restore and actual radial feedback. #348 orientation and #295 clipping remain separate; this repair does not claim them fixed.

## Crouch candidate delivered, 2026-09-08

Development build passed. Installed ASI and matching release manifest with RDR2 closed; SHA-256 `2108330DBEFE2A239ABD09FBF1CFF4DFDF7DEC5CC3C36715231155BFE866311D`. Prior ASI retained as a small rollback copy. No attachment settings, INI, catalog or save changes. Executable crouch policy test passes and rejects three mutations. Adjacent light and horse verifiers also pass; existing user-selected anchor differs from a legacy default verifier and was preserved. No game launch or visual acceptance claimed. Grey radial feedback remains unfinished; keep actionable.

Testable slice: in ordinary on-foot free roam with BeltLantern enabled, turn its light off through the radial. The unlit prop should remain. Crouch: dim light should appear. Stand: it should return off. Repeat from light on: crouch dims it and standing restores configured brightness. Check that mission lanterns remain untouched. This is not the complete issue acceptance test while radial feedback remains missing.
