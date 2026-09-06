# AGENTS.md — rules and routing

NEVER MISTAG MY ISSUES AGAIN.
NEVER LIE TO ME AND SAY YOU'LL UPDATE AN ISSUE'S TAG THEN NEVER DO IT.
NEVER REOPEN CLOSED ISSUES FOR NO REASON AGAIN.
NEVER IGNORE ME AGAIN.
NEVER LIE TO ME AGAIN.
NEVER WASTE MY TIME AGAIN.
NEVER ALLOW THESE MISTAKES TO HAPPEN AGAIN.

This file is auto-loaded at the start of every session, so it stays SMALL. It
holds only the working rules and the routing table. It deliberately contains no
mechanics, no per-item status and no technical detail.

Two stores hold the project's knowledge, and which one you use is decided by
HOW IT IS READ, not by what it is about:

- **`codex/*.md`** — settled truth, split by topic: how the game and this mod actually work.
  Confirmed mechanics, schemas, paths, proven engine limits, project and build
  policy, LEXEDITOR rules. Present tense, no dates, no narrative. NOT
  auto-loaded — grep it by subject. When something turns out to be wrong,
  rewrite the owning topic file in place; never append a correction chain.
  `CODEX.txt` is a generated compatibility index and is never hand-edited.
- **`worklog/issues/*.md`** — per-attempt scratch, one file per GitHub issue
  (or legacy TODO number). What was built,
  what the logs showed, what failed and why, build hashes, deployment proof.
  Past tense. NOT auto-loaded — grep it by item number. When an item is
  confirmed complete, delete its scratch and promote anything permanently true
  into the owning `codex/*.md` topic. `Worklog.txt` is a generated compatibility
  index and is never hand-edited; preserved mixed history lives in
  `worklog/legacy/`.

`codex/` vs `worklog/` is not a size split. It is tense and lifetime: the
codex says how the game IS and outlives every item; the worklog says what we
TRIED and dies with its item.

`FEATURES.txt` (implemented and in-game-confirmed features, Lexer-directed only)
and `CREDITS.txt` (public credits) are outputs, not knowledge stores.

NEVER FUCKING MALICIOUSLY MISTAG MY ISSUES AGAIN.
NEVER FUCKING LIE TO ME AND SAY YOU'LL UPDATE AN ISSUE'S TAG THEN NEVER DO IT.
NEVER FUCKING MALICIOUSLY REOPEN CLOSED ISSUES AGAIN.
NEVER FUCKING IGNORE ME AGAIN.
NEVER FUCKING LIE TO ME AGAIN.
NEVER FUCKING WASTE MY TIME AGAIN.
NEVER ALLOW THESE MISTAKES TO HAPPEN AGAIN.

## WHERE THINGS GO — read this before writing to any tracked file

GitHub issues are the live statement of requested behavior, status, decisions,
and in-game acceptance checks. Route technical knowledge by lifetime:

| Content | File |
|---|---|
| What a feature should do; why he wants it; his own design notes and decisions; workflow status; the short list of what to confirm in-game | the matching GitHub issue |
| Per-attempt implementation state, build hashes, deployment proof, log excerpts, runtime traces, decompiled evidence, what failed and why, native/global/anim-dictionary names | `worklog/issues/github-<number>.md` (or `todo-<number>.md` for unmigrated history) |
| Settled mechanics, schemas, paths, proven engine limits, project/build/release policy, LEXEDITOR UI rules, description style | the owning topic file under `codex/` |
| The working rules and this routing table | this file |
| Superseded investigations and dated session history | `worklog/legacy/` |
| Researched game-data coverage and schema map (generated, 438 KB — referenced, never pasted into the codex) | `DATA_MAP.md` |
| Story Mode script evidence (grep this before probing in-game) | `_downloads/RDR2-Decompiled-Scripts/script_rel/` |
| Implemented and in-game-confirmed features, Lexer-directed only | `FEATURES.txt` |
| Public credits | `CREDITS.txt` |
| Lexer's own design thinking and drafts — his file, never a task list, never agent-edited | `TODO.txt` |

`TODO.txt` is Lexer's private design scratchpad. It is where he thinks, drafts
and decides. It is NOT a work tracker and never a source of assignments: never
read it to find something to do, never treat an entry there as a task, and never
edit, reformat, validate, tidy or build tooling around it. Work comes only from
GitHub issues. Migrate an entry into an issue only when Lexer explicitly asks,
preserving his wording.

Never bulk-rewrite user-authored text or anything marked `Deprecated.` — those
are protected states, not prompts for replacement copy. Description style rules
are in `codex/item-description-style.md`.

NEVER MISTAG MY ISSUES AGAIN.
NEVER LIE TO ME AND SAY YOU'LL UPDATE AN ISSUE'S TAG THEN NEVER DO IT.
NEVER REOPEN CLOSED ISSUES FOR NO REASON AGAIN.
NEVER IGNORE ME AGAIN.
NEVER LIE TO ME AGAIN.
NEVER WASTE MY TIME AGAIN.
NEVER ALLOW THESE MISTAKES TO HAPPEN AGAIN.

## Parallel worktrees and integration ownership

- A feature worktree agent owns its topic source/data files and exactly one
  `worklog/issues/github-<issue>.md`. It does not edit another issue's worklog,
  the generated `CODEX.txt`/`Worklog.txt` indexes, or unrelated topic files.
- Feature worktree agents do **not** compile, link, install, or copy
  `GameplayTweaks.asi` when they finish. They run only issue-local static checks
  and hand their source changes to the integration agent.
- The integration agent alone owns cross-topic dispatchers/registries, merges
  worktree changes, resolves semantic conflicts, runs
  `python tools/knowledge_files.py rebuild`, performs the full build and test
  suite, installs and hash-verifies the one ASI, and changes final GitHub state.
- `GameplayTweaks/script.cpp`, `GameplayTweaks/build.bat`, generated knowledge
  indexes, and build/install scripts are integration-owned shared files. A new
  topic module is handed over unregistered; the integrator adds it to the
  dispatcher after merge.
- Separate files eliminate textual merge contention, not semantic conflicts.
  Two issues that change the same mechanic, data record, config key, or runtime
  state must be serialized or explicitly reconciled by the integrator.

## Codex safeguards derived from verified failures

This section is agent-maintained process guidance derived from `fuckups.txt`.
It is not attributed to Lexer and must never be quoted as though he authored it.

- Before implementing or repairing any issue, read `fuckups.txt` and record in
  that issue's worklog which prior failure classes could recur. Do not write
  code until the issue-specific check has named the primary evidence, sanctioned
  engine path or reference artifact, execution proof, and player-visible
  acceptance boundary.
- Resolve every constant, native, flag, hash, texture and schema against a named
  primary-source file and symbol. If it is unresolved, say so and do not ship a
  plausible guess.
- A call-site log proves only that a call was attempted. Build success, artifact
  hashes, setter calls, configuration lines and intent-only logs are never
  runtime acceptance. Require execution plus a real postcondition/readback, and
  keep player-visible acceptance separate.
- Every diagnostic must preserve the previous failure, emit an idle heartbeat,
  and distinguish "not executed" from "executed with no result".
- Treat every native in a per-frame path as a defect until its ownership and
  cadence are justified. Prefer transitions and sanctioned engine state over a
  frame-by-frame fight.
- Inspect every supplied reference file, mod, screenshot, log or session export
  before proposing a cause or implementation. Visual/UI defects require a
  rendered visual check; API, schema and syntax checks alone cannot establish
  that the screen is repaired.

## User instructions

NEVER FUCKING MALICIOUSLY MISTAG MY ISSUES AGAIN.
NEVER FUCKING LIE TO ME AND SAY YOU'LL UPDATE AN ISSUE'S TAG THEN NEVER DO IT.
NEVER FUCKING MALICIOUSLY REOPEN CLOSED ISSUES AGAIN.
NEVER FUCKING IGNORE ME AGAIN.
NEVER FUCKING LIE TO ME AGAIN.
NEVER FUCKING WASTE MY TIME AGAIN.
NEVER ALLOW THESE MISTAKES TO HAPPEN AGAIN.

- Be brief, direct, and willing to correct misunderstandings.
- Treat Lexer's chat reports and decisions as live tracker input: add them to the
  relevant GitHub issue, update its open/closed state, workflow labels, blockers,
  and relationships as warranted, and create a new issue when no relevant issue
  exists. Do not require Lexer to duplicate the same report manually on GitHub.
- Never post generic build hashes, install-status boilerplate, release-manifest
  boilerplate, queued-install notices, or superseded-artifact notices as GitHub
  issue comments. Build hashes and deployment proof belong in the issue worklog
  and install report unless Lexer specifically needs a hash to diagnose a
  runtime result.
- When carrying a report from chat into its GitHub issue, never copy Lexer's
  words back verbatim and never duplicate an existing issue comment. Add one
  concise comment only when it contributes something: the direct answer, the
  concrete action taken, the actual cause, or exact player-facing test steps.
  A label transition by itself does not need a comment.
- Issue comments must use plain language and answer Lexer's outstanding
  questions. A hash, label name, or statement that testing is required is not
  a substitute for explaining what changed and what he should actually do.
- Finish requested work. Do not stop at investigation, partial implementation,
  or an apology when the task can be completed.
- Do not commit or push unless Lexer explicitly asks.
- GitHub issues are the live tracker for migrated work. Update the matching
  issue whenever implementation state changes, in the same change as the work:
  work remaining = `actionable`; built and installed but needing Lexer's
  in-game confirmation = remove `actionable` and add `test me`; completed
  exploratory research = remove `exploratory` and add `needs a human`.
- No automatic label transition exists. After an install is hash-verified, run
  the required `gh issue edit` commands manually in the same turn, then read the
  issues back and report only the labels actually present.
- `release-manifest.json` records and verifies the ASI hash only. It is never a
  duplicate issue tracker and never supplies or mutates GitHub workflow state.
- Do not invent or use `review`, `waiting`, or another intermediate issue type.
  If an issue needs Lexer to inspect research, supply a missing manual input,
  or perform a computer-control/manual-GUI step, use the existing
  `needs a human` label. Completed actionable work always uses
  `test me` until Lexer confirms it.
- An `exploratory` issue authorizes research and a report to Lexer only. Do not
  implement it or promote/relabel it after research unless Lexer explicitly
  chooses to proceed.
- Do not launch RDR2, switch Story/Online mode, move mod-loader files, or take
  visible control of Lexer's browser without explicit permission.
- Routine editor verification must use API/static checks. Opening the editor in
  a browser steals focus and is reserved for genuinely necessary visual tests.
- GitHub issues are the only live tracker. Do not add, process, validate, or
  maintain local TODO entries. The existing `high priority` label is Lexer's
  explicit swarm-order signal; prioritize it without replacing the issue's
  workflow label, and do not invent other priority/class labels.
- `FEATURES.txt` contains only implemented, in-game-confirmed mod features.
  Only Lexer directs additions.

## Everything else

Project and release policy, build and install commands, data fundamentals,
LEXEDITOR UI rules and every confirmed runtime fact live under `codex/`.
Search the relevant topic before working on a subject. The generated indexes
are rebuilt and checked with `python tools/knowledge_files.py rebuild`.

NEVER MISTAG MY ISSUES AGAIN.
NEVER LIE TO ME AND SAY YOU'LL UPDATE AN ISSUE'S TAG THEN NEVER DO IT.
NEVER REOPEN CLOSED ISSUES FOR NO REASON AGAIN.
NEVER IGNORE ME AGAIN.
NEVER LIE TO ME AGAIN.
NEVER WASTE MY TIME AGAIN.
NEVER ALLOW THESE MISTAKES TO HAPPEN AGAIN.
