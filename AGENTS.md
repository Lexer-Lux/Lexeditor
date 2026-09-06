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

## GitHub issues are for humans

GitHub issues are for Lexer and other humans, not an agent's internal progress
tracker. Keep titles, bodies, and new comments brief. State the requested result,
the current status, and only the information needed to act. Game labels replace
game-name prefixes in titles. Preserve requirements, decisions, and reference
attachments when shortening an issue; move technical detail into the stores below.
Do not rewrite historical human comments or replace an unresolved request with a
smaller feature merely to declare it finished.

### Workflow labels

Every open issue has exactly one of these workflow labels. Keep game, bug,
enhancement, and priority labels separate from workflow status.

| Human status | GitHub label | Meaning |
| --- | --- | --- |
| Actionable | `actionable` | Agent work remains: research, implementation, repair, build, packaging, delivery, or preparing a usable test. This is the default for unfinished work. |
| Waiting | `waiting` | A specific action or answer from Lexer blocks the next meaningful step: a design choice, required asset, genuinely necessary permission, or a prepared diagnostic capture. The issue must say exactly what Lexer must do. |
| Needs Testing | `untested` | A specific implemented candidate is available to Lexer, relevant agent-side checks are complete, and only the described human test remains. `untested` is the existing label for Needs Testing, not a second status. |
| Unfeasible | `unfeasible` | Evidence establishes a specific limitation of the available technical path. Explain that limitation and what would have to change. This does not mean universally impossible. |

**Waiting means WAITING ON LEXER.** It never means low priority, expensive,
difficult, not selected this session, out of time/tokens/budget, not yet researched,
awaiting another agent, or simply something an agent does not want to do. Those
issues stay `actionable`. Do not manufacture a design question or ask for approval
again when Lexer has already supplied the decision or authorized the work.

An explicit user instruction to defer implementation must still be respected,
but it is a scheduling constraint, not automatically a `waiting` label. Record
that constraint briefly; do not disguise unfinished work as a human blocker.
Changing a workflow label does not authorize implementation outside the request.

### Required actions and test readiness

- Every `waiting` issue ends with an unchecked checklist of the exact actions or
  answers needed from Lexer. Design questions belong there, not a pretend test.
- Every `untested` issue ends with an unchecked test checklist: available build or
  candidate, setup, controls/steps, expected visible result, and what to report.
  Keep it short and reproducible. Supply fixtures, saves, tools, or diagnostics
  first when the test needs them; do not make Lexer invent the test or build code.
- A source patch, passing CI, draft PR, queued build, or unconfirmed install is
  not a delivered test candidate. Missing build/delivery/test preparation keeps
  the issue `actionable`, not `waiting` or `untested`.
- A failed player test returns to `actionable`. Do not request the same test again
  until a relevant change or a genuinely new, prepared diagnostic justifies it.
- If agent work still remains within the issue's scope, keep it `actionable` and
  distinguish any testable slice. Do not hide unfinished parts behind a test label.
- Lack of investigation or unsuccessful attempts alone do not prove `unfeasible`.
  A rejected design or cancelled request is not a technical impossibility.
- Before changing status, re-read the live body and comments, then check relevant
  code, PRs, and internal worklogs. Apply the latest human decisions and failures;
  never infer installation, in-game success, or approval from static checks.
- Close as completed only when the requested scope is actually confirmed done.
  Remove `actionable`, `waiting`, and `untested` from closed issues. Use the correct
  closure reason for cancelled or duplicate work; do not call it implemented.

## Internal knowledge and progress

- Keep confirmed mechanics, schemas, paths, and engine limits in topic files
  under `codex/`. Write current facts; replace incorrect facts in place.
- Keep internal implementation progress, remaining agent steps, attempts, logs,
  hashes, failures, deployment evidence, and test preparation in
  `worklog/issues/github-<number>.md`. Read and update the relevant worklog during
  work. These are the agent handoffs; do not paste them into GitHub issues or use
  human-facing labels to conceal unfinished internal work.
- When an issue is confirmed complete, move lasting knowledge into `codex/`
  and remove its temporary worklog. Keep historical handoffs in `worklog/legacy/`.
- These stores are searched when needed, not loaded in full every turn.
