# #21: Finish and validate FF8 plugin coverage

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/21)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

2026-09-08 Refine save repair: recipe IDs and numeric fields require actual
integers; fractions, booleans, and strings cannot silently select a different
recipe or change its quantity. Recipe text requires text instead of converting
arbitrary request values. Each changed table is decoded again before returning
the rebuilt bytes.

Four synthetic tests cover numeric edits, text growth and linked offsets,
reserved-byte preservation, malformed requests, and fixed-section overflow.
All FF8 Python tests passed: 62 tests and 110 subtests. The existing
`tools/verify_ff8_refine_tables.py` passed checks on all 377 recipes, isolated
service saves of numeric/text changes in all five tables, baseline preservation,
and the headless editor. No game acceptance is implied.

Refine layout repair: editable input/output selections and quantities now stay
in the selected recipe's detail pane. The master list keeps ID, ability, and
recipe identity. The existing five-barrel option remains. The headless verifier
now asserts no list editors, two usable quantity controls, and persisted detail
quantity/text edits. All five tables, five-barrel geometry, and the updated
rendered check pass; the generated screenshot was inspected. Shared property
labels still use the narrow global label lane at minimum detail width.

## Next agent work

The parent issue remains actionable. Its unfinished runtime/features and human
gameplay acceptance remain in scope. Load the repaired local service before
testing Refine in game; no user app or game was restarted by these checks.

## 2026-09-22 misc-fixes note
Coverage parent: no direct work here. Children are being processed on PR 506 (#31, #84, #91, #308 plus #407-409 and #93/#100 pending). The plugin is ready only when the children close with acceptance, not when tabs exist. Issue stays actionable.

Draw-check slice done on PR 506 (b338b02a): tests/test_ff8_streamlined_draw.py, 7 green. Refine tables covered (4 tests). Text-override slice done on PR 506 (c8a8183a): tests/test_ff8_kernel_text.py, 7 green, including a pinned apostrophe asymmetry (encode ' decodes U+2018, benign).

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
