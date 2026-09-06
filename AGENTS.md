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

## GitHub issues are the source of truth

GitHub issues and their comments are the canonical record of requests and public
project discussion. Agents may summarize implementation state in an internal
handoff, but must not mirror or archive complete issue bodies, comments, attachment
files, screenshots, or GitHub API metadata into this repository.

- Keep one current implementation handoff at `worklog/issues/github-<number>.md`
  when an issue needs internal continuity. It should contain current requirements,
  implementation state, evidence, and next work; it is not a verbatim issue archive.
- Read the live GitHub issue and comments before changing scope or status. Use
  available chat/file context and relevant codex topics when needed.
- Never create `worklog/attachments/`, `worklog/issues/github-*/sources/`,
  `worklog/issues/github-*/conversation.md`, or `worklog/migrations/comment-archive/`.
- Never download GitHub issue attachments into the repository merely for archival
  or provenance purposes. Project assets intentionally used by Lexeditor are a
  separate category and belong in their normal project asset paths.
- Never delete issue comments as part of cleanup, summarization, handoff, or
  archival. Comments remain on GitHub unless Lexer explicitly asks to remove a
  particular comment.
- Never delete whole issues as a substitute for tidying worklogs or project history.

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
- Re-read the live issue, relevant code/PRs, worklogs, and codex before changing
  status. Never infer delivery, in-game success, or approval from CI.
- Close as completed only when the requested scope is confirmed done. Remove
  active workflow labels on closure and use truthful duplicate/cancellation reasons.

## Central knowledge and parallel work

- Lexeditor owns the canonical game knowledge: `codex/<game>/README.md` plus
  topic files under `codex/<game>/`. Shared editor knowledge uses `codex/shared/`.
- Lexeditor also owns the canonical implementation worklogs under `worklog/`.
  Standalone `Lexers-Mod-*` repositories are storage/distribution repositories;
  they must not recreate independent Codex, Worklog, project-memory, or issue-history
  stores. Their `AGENTS.md` files should direct development back here.
- Codex contains settled mechanics, schemas, paths and demonstrated limits.
  Attempts, guesses, current progress and pending work stay in concise per-issue
  worklogs. The live GitHub issue remains the canonical request/discussion record.
- One issue owner edits its handoff. Parallel contributors should avoid competing
  global Worklog files; one integrator reconciles shared codex indices and handoffs.
- On imports from standalone mod repositories, import only actual game-development
  notes that are not already centralized here. Do not import GitHub issue mirrors,
  attachment caches, generated API snapshots, or forwarding stubs as knowledge.
- Before retiring a legacy Codex/Worklog store in a standalone mod repository,
  verify useful development knowledge is accounted for centrally, then remove the
  old store and keep only the repository's storage-only `AGENTS.md` guidance.
- Review private-source documentation before publishing into this public repo.
  Never include credentials, private binaries, proprietary game dumps or unrelated
  personal data. A public repository is not private merely because agents use it.
- These stores are searched when needed, not loaded in full every turn.
