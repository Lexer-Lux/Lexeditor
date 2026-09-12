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
