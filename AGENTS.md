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
game-name prefixes in titles. Brevity applies to the public summary, NEVER to
preservation of the specification. Do not replace an unresolved request with a
smaller feature merely to declare it finished.

### Lossless capture comes before summarization

- When Lexer supplies a request, preserve their complete wording, examples,
  numbers, exceptions, rejected alternatives, attachments, and later corrections
  before creating or shortening its GitHub summary. Save verbatim text, not
  another paraphrase. Never label reconstructed text as an original quotation.
- Each issue has one internal handoff: `worklog/issues/github-<number>.md`.
  Its immutable source records live beside it in
  `worklog/issues/github-<number>/sources/`. Use a temporary request identifier
  before an issue number exists, then link it when the issue is created.
- Keep an explicit requirements/acceptance section in the handoff, traceable to
  the source records. A short current summary does not cancel archived scope.
  Resolve contradictions using the latest explicit human decision; preserve the
  superseded instruction as history instead of silently erasing it.
- Before saying context is missing, search the issue's source records and
  comments, transferred issue IDs, legacy Worklog/TODO/GOAL files, relevant game
  codex, and available original chat/file sources. Record what was searched.
  A short or blank GitHub body is NOT evidence that Lexer supplied no details.
- If the original request was lost or has not been retrieved, own that as
  retrieval/recovery work (`actionable`), not as a failure by Lexer to explain.
  Ask only about a genuinely unresolved point after recovering existing context.

### Workflow labels

Every open issue has exactly one of these workflow labels. Keep game, bug,
enhancement, and priority labels separate from workflow status.

| Human status | GitHub label | Meaning |
| --- | --- | --- |
| Actionable | `actionable` | Agent work remains: context recovery, research, implementation, repair, build, packaging, delivery, or preparing a usable test. Default for unfinished work. |
| Waiting | `waiting` | A specific action or answer from Lexer blocks the next meaningful step: a genuinely unresolved design choice, required asset, necessary permission, or prepared diagnostic capture. |
| Needs Testing | `untested` | A specific candidate is available to Lexer, relevant agent-side checks are complete, and only the described human acceptance test remains. |
| Unfeasible | `unfeasible` | Evidence establishes a specific limitation of the available technical path. Explain the limitation and what must change; this is not a claim of universal impossibility. |

**Waiting means WAITING ON LEXER.** It never means low priority, expensive,
difficult, not selected this session, out of time/tokens/budget, not researched,
awaiting another agent, missing local access, or something an agent does not want
to do. Those issues stay `actionable`. Do not manufacture a design question or
request approval again when Lexer already decided or authorized the work.

Respect explicit user deferrals, but record them as scheduling constraints, not
automatically as `waiting`. Changing status does not authorize unrelated work.

### Required actions and test readiness

- Every `waiting` issue ends with an unchecked checklist of the exact actions or
  answers needed from Lexer. Design questions are not pretend gameplay tests.
- Every `untested` issue ends with a short, reproducible checklist: available
  candidate, setup, controls/steps, expected result, and what to report. Supply
  needed fixtures, saves, tools and diagnostics first. Lexer does not build code
  or invent acceptance tests on the agent's behalf.
- A source patch, passing CI, draft PR, queued build, or unconfirmed installation
  is not a delivered candidate. Missing preparation/delivery stays `actionable`.
- A failed human test returns to `actionable`. Do not repeat it without a relevant
  change or a genuinely new prepared diagnostic.
- If work remains within the requested scope, retain `actionable` and identify
  any testable slice separately. Do not hide unfinished scope behind a test label.
- Unsuccessful attempts or lack of investigation do not prove `unfeasible`.
  Rejected designs and cancelled requests are not technical impossibilities.
- Re-read live source records, comments, relevant code/PRs and worklogs before
  changing status. Never infer delivery, in-game success or approval from CI.
- Close as completed only when the requested scope is confirmed done. Remove
  active workflow labels on closure and use truthful duplicate/cancellation reasons.

### Archive first; clean the visible discussion second

Lexer authorizes moving issue discussion into the internal records and deleting
archived comments to keep GitHub concise. This supersedes the earlier instruction
to keep all historical comments visible. It does NOT authorize losing their content.

- Archive every original body/comment version verbatim, including source URL,
  author, ID, timestamps, attachments and a content hash. Preserve before-edit
  text from webhook events and earlier snapshots when available.
- Commit and verify the archive in the canonical repository BEFORE deleting any
  comment. A local scratch file or expiring Actions artifact alone is insufficient.
- Re-read each comment before deletion. Skip new or changed records that are not
  the exact archived version. Skip records whose required attachments cannot be
  preserved. Never delete whole issues, PR reviews or unrelated repository data
  as a substitute for cleaning issue comments.
- Technical attempts, stack traces, hashes and discussion history belong in the
  internal worklog/source records, not in repeated GitHub comments. Keep the live
  issue's current result, real status, and required human checklist concise.
- Completion may retire the active handoff, but never delete the original request,
  decisions or evidence archive. Retain them under `worklog/legacy/` if moved.

## Central knowledge and parallel work

- Lexeditor owns the canonical game knowledge: `codex/<game>/README.md` plus
  topic files under `codex/<game>/`. Shared editor knowledge uses `codex/shared/`.
  Mod repositories may link here; they must not become independent competing
  sources of truth. Existing paths remain readable during migration.
- Codex contains settled mechanics, schemas, paths and demonstrated limits.
  Attempts, guesses, current progress and pending work stay in per-issue worklogs.
  Imported historical notes are provenance, not automatically current fact.
- One issue owner edits its handoff. Parallel contributors append uniquely named
  source/session records; one integrator reconciles the handoff. Do not have every
  agent rewrite a global Worklog.txt or shared codex index.
- Record source repository, branch/commit, original path and content hash on
  import. Snapshot now; after parallel branches merge, import only new/changed
  records and reconcile conflicting facts. Never overwrite central newer work
  with an older source copy, force-push, or delete another worker's notes.
- Before retiring a legacy store, verify every source file is accounted for and
  leave a forwarding pointer. Do not claim uncommitted local work was migrated
  through GitHub; preserve it through an explicit local import when accessible.
- Review private-source documentation before publishing into this public repo.
  Never include credentials, private binaries, proprietary game dumps or unrelated
  personal data. A public repository is not private merely because agents use it.
- These stores are searched when needed, not loaded in full every turn.
