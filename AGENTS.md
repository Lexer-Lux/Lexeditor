# Lexeditor project rules

- Every game plugin must expose a Data Map screen. Do not use a generic Files
  tab as the player-facing editor for data that needs a format-specific view.
- Always use the most appropriate HTML control for the value. Use checkboxes
  for booleans, bounded number controls for numeric ranges, and selects for
  known enums. Do not use a free text or unbounded number input when the data
  schema provides a finite choice or a valid range.
- Keep list and detail views consistent with the RDR2 plugin: record identity
  stays in the master list, and all editable fields stay in the selected
  record's detail pane.
- Do not claim visual acceptance from source, API, or smoke checks.

## GitHub issues and internal knowledge

- GitHub issues are for Lexer to read and respond to. Keep titles, bodies,
  and comments short. Include the requested behavior, relevant status,
  decisions, and only the information needed to act. Game labels replace
  game-name prefixes in titles.
- Use `waiting` only when a specific action or answer from Lexer blocks work.
  Every waiting issue must end with an unchecked checklist of those actions.
  For a test, give the exact setup, steps, expected result, and what to report.
  Prepare the test first. Do not make Lexer work out how to validate a feature.
  If agent work remains before Lexer can act, use `actionable` instead.
- Keep confirmed mechanics, schemas, paths, and engine limits in topic files
  under `codex/`. Write current facts; replace incorrect facts in place.
- Keep implementation attempts, logs, hashes, failures, deployment evidence,
  and test preparation in `worklog/issues/github-<number>.md`. Search these
  files before work on an issue. Do not paste them into GitHub issues.
- When an issue is confirmed complete, move lasting knowledge into `codex/`
  and remove its temporary worklog. Keep historical handoffs in `worklog/legacy/`.
- These stores are searched when needed, not loaded in full every turn.
