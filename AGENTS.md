# Lexeditor project rules

- Reuse existing controls, panel functions, layouts, and CSS classes. When two
  screens show the same kind of data, use one component and one set of sizing
  rules. Fix that component and check each caller before adding a screen override.

- Before creating a new game plugin, read `docs/ADDING_A_GAME.md` and follow its
  research-first workflow. Survey existing open-source tools/loaders, documentation
  and format knowledge before writing new parsers, and record material sources in
  Credits as they are used rather than reconstructing provenance later.
- Branches are fine; leftovers are not. When a task is done and verified, merge
  its branch into master and delete the branch, its worktree and any stash in
  the same session. Never leave finished work parked where Lexer has to find
  it, and say plainly if you stop with unmerged work. Pushing needs Lexer's
  explicit go-ahead.
- Every game plugin must expose a Data Map screen. Do not use a generic Files
  tab as the player-facing editor for data that needs a format-specific view.
- Always use the most appropriate HTML control for the value. Use checkboxes
  for booleans, bounded number controls for numeric ranges, and selects for
  known enums. Do not use a free text or unbounded number input when the data
  schema provides a finite choice or a valid range.
- Keep list and detail views consistent with the RDR2 plugin: record identity
  stays in the master list, and all editable fields stay in the selected
  record's detail pane.
- Give editor tabs, sections, and fields shared question-mark help. Explain the
  gameplay effect, how to use the control, and any known limits in plain language.
  File offsets and parser details are not a substitute for user instructions.
- Necessary information belongs in the question-mark help, not in a paragraph
  on the page. A panel body carries controls and data: counts, coverage,
  limits, caveats and the word "disclaimer" go into that panel's own help
  bubble. A visible note is only for a state the reader must act on now, such
  as an error, a missing file, or a table with nothing to show yet.
- Do not claim visual acceptance from source, API, or smoke checks.

## Muse use

- Do not use Muse by default. Lexer withdrew that preference because its
  delays and repair work did not save enough time. Make edits directly unless
  Lexer asks to try Muse again. The instructions below apply only to such a
  requested trial; the primary agent still owns diagnosis and verification.
- Use headless execution: `muse exec --workspace C:\Lexeditor --prompt-file
  <prompt-path> --max-model-steps 20`. Put temporary prompts and output outside
  the checkout. Use the current checkout path if it differs from this example.
- Give each task the exact files it may edit, the required behavior, the shared
  components it must reuse, and the checks it must pass. State what it must
  preserve. Do not send the whole issue backlog as one task.
- Muse must not delegate again, widen the task, change unrelated files, commit,
  merge, push, or change issue status. Avoid concurrent edits to the same files.
- Review every changed line and run the relevant checks yourself. For UI work,
  inspect the rendered result and test the interaction. Muse's report is not
  proof that the task is complete.
- If Muse stalls or misses the requirement, give it one precise correction or
  take over the edit. Use direct edits when delegation would cost more work
  than the change itself. Do not repeat failed attempts without new evidence.

## GitHub issues are the source of truth

### Standard plugin issue structure

Use one parent issue titled `Plugin`, identified by its game label. Link these
four actual subissues in this order, with the same game label on each:

1. `Create Editor`: Research existing tools and format knowledge first. Build
   the plugin and required code, vendor permitted helpers, and record Credits.
   Integrate every Data Map area with appropriate editable views. Do not hide
   unsupported rows or call raw-file access full integration. Only Lexer can
   exclude areas as not worth the effort; ask when scope or value is in doubt.
   Unknown semantics remain protected until proven; report the gap, not success.
2. `Implement Mod Loading`: Find, add, load and remove real mods. Support record
   overrides and composition against vanilla where the format requires them,
   rather than silently replacing a whole file for unrelated record changes.
   Define load order, conflicts, dependencies and restoration. Test a documented
   range of real online mods in isolation, including overlapping edits, and
   make supported mods work without manual repair. Record unsupported cases.
3. `Create Theme`: Use the game's fonts, colours and sound effects for a fitting
   theme. Record asset provenance and distribution rights; extract locally when
   redistribution is not permitted. Do not publish proprietary assets blindly.
4. `Create GUI`: Build usable, human-friendly screens with shared controls,
   clear help and good navigation. Inspect rendered screens and interactions,
   repair UI defects, and check small windows and large UI scales.

Reuse existing matching issues and preserve their discussion. These four
subissues track one plugin, not four separate efforts.
Keep game names out of issue titles. Each open issue needs its own truthful
workflow label. Source, rendered UI, mod compatibility, delivered candidate and
in-game acceptance are separate checks; the parent is not complete while required
scope remains. Do not infer permission to merge from completion.

Issue/PR administration belongs here. Keep private worker coordination, chat
URLs, monitoring, recovery and cleanup out of `docs/ADDING_A_GAME.md`; that guide
is the public technical methodology for users and their agents.

GitHub issues and their comments are the canonical record of requests and public
project discussion. Agents may summarize implementation state in an internal
handoff, but must not mirror or archive complete issue bodies, comments, attachment
files, screenshots, or GitHub API metadata into this repository.

- Game-specific issues must carry the appropriate game label. Apply the game
  label when the issue is created rather than encoding game identity in its title.
- Do not prefix or suffix issue titles with a game name or abbreviation (for
  example `FF7R:` or `FF8:`). The game label identifies the plugin; the title
  describes only the requested work.
- If a required game label is missing, add/apply it before treating the issue as
  correctly filed. Do not substitute a game-name title prefix for a missing label.
- Keep one current implementation handoff at `worklog/<number>.md`
  when an issue needs internal continuity. It should contain current requirements,
  implementation state, evidence, and next work; it is not a verbatim issue archive.
- Read the live GitHub issue and comments before changing scope or status. Use
  available chat/file context and relevant codex topics when needed.
- `worklog/` is flat: one `<number>.md` per issue and nothing else. Never add
  subfolders, screenshots, attachments, imported mirrors or API dumps there.
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
- A candidate is a pushed master commit that Lexer runs with `Lexeditor.cmd`
  (the app updates itself from master). A local commit, passing CI, or an
  unconfirmed installation is not a delivered candidate. Missing
  preparation/delivery stays `actionable`. Do not build packaged test bundles.
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

- Lexeditor owns the canonical game knowledge under `codex/<game>/`. Write a
  page only for something proven and expensive to rediscover; never create
  placeholder pages. Shared editor knowledge uses `codex/shared/`.
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

## Checks

- Every plugin's checks run with `python tools/check_plugin.py <plugin>`, and
  shared ones with `--global`; CI runs exactly these, one generated
  `<plugin>-checks.yml` per plugin plus `global-checks.yml`. Put a new test in
  `tests/<plugin>/` (the plugin's folder name) as `test_*.py` (pytest),
  `verify_*.py` or `*_check.py` (script); checks that belong to no plugin go
  in `tests/shared/`. Nothing else sits loose in `tests/`, and file names stay
  unique across its folders. A file that imports a helper from another
  `tests/` folder puts that folder on `sys.path` itself. Do not hand-write
  workflows; after adding a plugin run
  `python tools/check_plugin.py --write-workflows`.
- `tools/` holds project utilities people run. Checks, verifiers and their
  helpers belong in `tests/`; one-off probes are deleted when their issue
  closes.

## Temporary storage and local checks

- The checkout holds source only. Never create `_scratch/`, `.pytest_cache`,
  `artifacts/`, `out/` or other working folders in it; `tests/shared/test_repo_hygiene.py`
  fails when one appears. Use your own session scratchpad, or
  `%TEMP%/lexeditor-dev` for dev caches shared between checks (upstream
  source clones, verifier results, screenshots).
- Use temporary directories with guaranteed cleanup for disposable build and
  browser work. Keep final source patches and small reports outside those trees.
- Never build, clone upstream sources or keep browser profiles inside the
  repository; an abandoned 16 GB FFNx build tree once made the checkout 18 GB.
  Delete what you put in temp folders before you finish.
- Anything the app writes to a player's disk (backups, caches, previous
  copies) needs a bound: keep the original plus the newest, or cap the size and
  evict. An unbounded timestamped copy per action is a bug.
- Before a large build or download, check free space and state the expected disk
  cost. After the job, remove only its generated files. Preserve source changes,
  mods, saves, required game data, and diagnostic evidence that is still needed.
- Do not open visible test windows during a routine check. Native window
  fixtures require explicit user approval; headless checks are the default.

## Editing files from a shell

- Do not pass code containing quotes or backslashes through a bash heredoc.
  Escaping inside `<<'PY' ... PY` fails on the outer shell first, which reads as
  ``unexpected EOF while looking for matching `'``. Write the patch script to
  the scratchpad with the file-writing tool, then run it: `python
  <scratchpad>/patch.py`. Same for one-off checks longer than a single line.
- A patch script asserts what it expects to find before replacing it, so a
  changed file fails loudly instead of silently matching nothing.

## Actionable-to-waiting handoff

- Work every open actionable issue you can: verify the code, run `python tools/check_plugin.py <plugin>`, and record evidence plus human test plans (or blocked findings with proof) in the per-issue handoff. Close nothing without a delivered candidate; once one is pushed, move the issue to `untested` yourself.
- When agent work is done and only a specific Lexer action blocks the next step, flip the issue to waiting: append an unchecked checklist of the exact actions or answers needed from Lexer and swap the actionable label for waiting. Everything else keeps actionable.
