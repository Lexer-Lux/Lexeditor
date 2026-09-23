# #121: Design reliable continuous saving without reload undo

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/121)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 concrete design prepared

Read live #121 and comments, current save-owner source and prior progression-loss record. Design: [continuous saving](../../docs/rdr2-continuous-saving-design.md). It covers request/acknowledgement sequencing, consequences, death/arrest/checkpoints, crash recovery, all normal load entry points, development recovery and bounded storage. Local1491.50 long_update source SHA-256: 881DECB771F95139FC199970CBD7F190354077F5A48C51226B27EE7565024940. Functions110/501/506/508/1313/1314 establish the engine preparation/request/snapshot boundaries; save_menu_ui_event_handler alone is not a correlated durable acknowledgement.

Next: read-only request/completion observer and proved idempotent consequence handling. Crash during a save-blocked mission remains a substantive gap; periodic autosaving does not satisfy the full request. No real saves were read or modified. No runtime feature installed. Remains actionable.

## 2026-09-22 misc-fixes note
Design doc exists (docs/rdr2-continuous-saving-design.md) with engine boundaries and a known gap (crash during a save-blocked mission). Next: read-only request and completion observer plus proved idempotent consequence handling. No saves touched, no runtime installed. Issue stays actionable.

## 2026-09-23 master: reviewed for waiting flip, stays actionable

No concrete Lexer-side session exists yet (agent-side previews/prototype
still owed), so flipping to waiting would be a fake checklist. Left
actionable until a real session can be written.

## 2026-09-23 agent review (per-game-rdr2): no new agent-side slice, stays actionable

Re-read the live issue plus comments. The design exists
(docs/rdr2-continuous-saving-design.md) with engine boundaries and the
known save-blocked-mission crash gap. Exact needs: Lexer design approval,
then a read-only request/completion observer plus proved idempotent
consequence handling, with no save mutation until then. No code written here.

## 2026-09-23 agent slice (impl/rdr2-actionables): design acceptance contract

plugins/rdr2/continuous_saving.py records the design's acceptance
checklist as data (six design sections plus the seven consequence rows
from the design table) with validate_saving_plan(), which rejects
periodic-autosave-only, generic inventory-difference replay, and
uncorrelated SAVE_COMPLETE acknowledgement, and blocks real-save
mutation before design approval. Covered by
tests/test_rdr2_continuous_saving.py (8 hermetic tests). No gameplay
claim: design approval, the read-only observer, and the
save-blocked-mission crash gap still need the game.

