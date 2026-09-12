# #84: Finish map, field and enemy-AI editing coverage

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/84)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

2026-09-08 local enemy-AI repair: branches to the script end now use `END` in
source and `end` in the compiler. They survive source/structure round trips and
instruction insertion. Invalid branch destinations remain readable without a
source form. Operand and structural writes reject destinations inside operands
or outside the script. Fractional operands are rejected, not truncated. New
local-variable instructions start with a valid listed variable.

Checks: `tests/test_ff8_enemy_ai.py` passed 7 tests and 69 subtests. All 144
available baseline enemy DAT files retained exact bytes after both source and
structure round trips. `tools/verify_ff8_enemy_ai_source.py` passed its 11,763-line
corpus check, isolated service save/readback, and headless source-editor test.
The generated editor screenshot was inspected. This does not prove gameplay.
Adjacent formula, GF spellbook, and field-asset tests passed (20 tests).

Field save repair: validate all maps before writing any destination. If a later
write fails, restore the earlier files and remove new files from that request.
Rollback does not create more backup copies. This handles reported write errors,
not power loss or process termination. New automatic backups use one latest
`<field filename>.lexeditor-auto.bak` per file. Existing historical backups stay
untouched. Unchanged saves do not write files or create backups. A failed rollback
keeps the original save error as its cause.
Six synthetic tests cover later-map validation failure, disk write failure,
existing/new file rollback, duplicate destinations, successful multi-map save,
100 changed saves with bounded storage, 100 unchanged saves with no writes, and
error chaining. All FF8 Python tests pass: 58 tests and 76 subtests.
`tools/verify_ff8_field_encounter_editor.py` passed the real isolated
service save, readback, reference/vanilla controls, and semantic MRT/RAT merge.

## Next agent work

Issue remains actionable. World marker placement, Draw Point imagery, the
textured 3D toggle, 4×4 palette controls, field-local detail tabs, and full
in-game enemy-AI acceptance remain in scope. No user game or open editor was
restarted. Reload the local plugin to load this Python repair.
