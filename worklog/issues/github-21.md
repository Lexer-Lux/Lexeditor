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
