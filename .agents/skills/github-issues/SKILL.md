---
name: github-issues
description: Lexeditor's GitHub issue rules. Use before creating, labelling, re-labelling, test-planning, closing or reporting status on any issue, and before writing worklog/<number>.md handoffs.
---

# GitHub issues

GitHub issues and their comments are the canonical record of requests and
discussion. Read the live issue and its comments before changing scope or
status.

## Filing

- Game-specific issues carry the game label (the plugin id), applied at
  creation. Titles never carry a game name or abbreviation (`FF7R:`, `FF8:`);
  if the label is missing, add it rather than prefixing the title.
- Reuse existing matching issues and preserve their discussion.
- Game plugin parents and their five subissues: see
  `.agents/skills/add-game/SKILL.md`.

## Workflow labels

Every open issue has exactly one of these, except a `Plugin` parent, which has
none. Game, bug, enhancement and priority labels are separate from status.

| Status | Label | Meaning |
| --- | --- | --- |
| Actionable | `actionable` | Agent work remains: research, implementation, repair, build, delivery, or preparing a usable test. Default for unfinished work. |
| Waiting | `waiting` | A specific action or answer from Lexer blocks the next step: an unresolved design choice, required asset, permission, or prepared diagnostic capture. |
| Needs Testing | `untested` | A delivered candidate exists, agent-side checks are done, and only the described human acceptance test remains. |
| Unfeasible | `unfeasible` | Evidence shows a specific limitation of the available technical path. Say what the limitation is and what would have to change. |

**Waiting means waiting on Lexer.** It never means low priority, expensive,
difficult, out of time or tokens, not researched, waiting on another agent, or
unwanted. Those stay `actionable`. Do not invent a design question or ask again
for approval Lexer already gave. An explicit deferral from Lexer is a
scheduling note, not automatically `waiting`.

## Moving between labels

- Work every actionable issue you can: verify the code, run the one covering
  check locally, read CI for the rest, and record evidence in the handoff.
- **To `waiting`:** only when agent work is done and a specific Lexer action
  blocks the next step. End the issue with an unchecked checklist of the exact
  actions or answers needed. Design questions are not pretend gameplay tests.
- **To `untested`:** only with a delivered candidate, which is a pushed master
  commit that Lexer runs with `Lexeditor.cmd` (the app updates itself from
  master). A local commit, passing CI or an unconfirmed install is not a
  candidate. End the issue with a short reproducible checklist: candidate,
  setup, steps, expected result, what to report. Supply the fixtures, saves,
  tools and diagnostics first; Lexer does not build code or invent tests. Do
  not build packaged test bundles.
- If work remains within scope, keep `actionable` and describe any testable
  slice separately. Do not hide unfinished scope behind a test label.
- A failed human test returns to `actionable`. Do not repeat it without a
  relevant change or a genuinely new diagnostic.
- Failed attempts or missing investigation never prove `unfeasible`. Rejected
  designs and cancelled requests are not technical impossibilities.
- Never infer delivery, in-game success or approval from CI.
- Close as completed only when the requested scope is confirmed done. Remove
  the workflow label on closure and use truthful duplicate/cancellation
  reasons.

## Worklogs

- One current handoff per issue at `worklog/<number>.md`, only when the issue
  needs internal continuity: current requirements, state, evidence, next work.
  One issue owner edits it.
- `worklog/` is flat: `<number>.md` files and nothing else.
- Never mirror issue bodies, comments, attachments, screenshots or API
  metadata into the repository, and never download attachments for archival.
  Project assets Lexeditor actually uses go in their normal asset paths.

## Never

- Delete issue comments, unless Lexer asks for a particular one.
- Delete whole issues to tidy history.
