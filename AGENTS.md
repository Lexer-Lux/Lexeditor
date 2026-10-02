# Lexeditor project rules

These rules apply to every task. Longer procedures live in skills under
`.agents/skills/`. Read the matching `SKILL.md` before starting that kind of
work, even if your tool does not load skills on its own.

| Before you... | Read |
| --- | --- |
| file, relabel, test-plan or close a GitHub issue, or write `worklog/` | `.agents/skills/github-issues/SKILL.md` |
| start, scope or file issues for a game plugin | `.agents/skills/add-game/SKILL.md` |
| add, change or review help bubbles or Data Map descriptions | `.agents/skills/help-text/SKILL.md` |
| write `codex/`, or import from a `Lexers-Mod-*` repository | `.agents/skills/knowledge/SKILL.md` |

## Editor UI

- Reuse existing controls, panel functions, layouts, and CSS classes. When two
  screens show the same kind of data, use one component and one set of sizing
  rules. Fix that component and check each caller before adding a screen override.
- Always use the most appropriate HTML control for the value: checkboxes for
  booleans, bounded number controls for numeric ranges, selects for known
  enums. No free text or unbounded number input when the schema gives a finite
  choice or a valid range.
- Keep list and detail views consistent with the RDR2 plugin: record identity
  stays in the master list, and all editable fields stay in the selected
  record's detail pane.
- Give a field, section or tab a question-mark bubble only when its label and
  control do not already say everything. Write it per the help-text skill.
- Necessary information belongs in the question-mark help, not in a paragraph
  on the page. Counts, coverage, limits, caveats and disclaimers go into that
  panel's help bubble. A visible note is only for a state the reader must act
  on now, such as an error, a missing file, or an empty table.
- Never create a mod the reader did not ask for. Opening a game lands on the
  game's own data, read-only, and the mod selector names that source Vanilla;
  creating or copying a mod is an explicit action. An edit attempt in that
  state offers to create one. See `codex/shared/no-mod-state.md`.
- Every game plugin exposes a Data Map screen. A generic Files tab is not the
  player-facing editor for data that needs a format-specific view.
- Do not claim visual acceptance from source, API, or smoke checks. Look at the
  rendered screen.

## Game patches

- Hext first. A change to how a game behaves, including calling the game's own
  routines, is a Hext patch. Reach for a custom native driver (FF8's FFNx
  derivative and the like) only when Hext cannot do the job well: drawing the
  game has no routine for, renderer or frame-rate work, file I/O, or logic too
  large to keep correct in hand-written assembly. Say which of those applies
  when adding driver code.
- In-game messages use the game's own message box, never an overlay imitation.

## Tweaks

- A **tweak** is an ordinary mod in the reader's mod library, never code in this
  repository. It carries its own files: a build script (`script/tweak.py`),
  its settings schema and values, and whatever the game loads (Hext, ASI, DLL,
  INI section, data files). Enabling or disabling the mod is the toggle.
- A tweak whose patch depends on settings is a **tweak mod**
  (`core/script_mods.py`): the game's mod loader runs its trusted script with
  the reader's values when applying, then deploys what it built like any other
  mod file. The Tweaks page renders every tweak from its schema; do not build a
  bespoke settings surface for one tweak.
- Each game's loader builds and deploys tweak mods its own way (FF8:
  `plugins/ff8/tweak_mods.py`). A tweak's code, built payloads and tests live in
  the mod (and later Lexer's mod repository for that game);
  `tests/shared/test_no_tweak_payloads.py` keeps them out of here.
- When an issue says a change "should be a tweak," make it a tweak mod and keep
  vanilla behavior when the mod is disabled.

## Git and publishing

- Branches are fine; leftovers are not. When a task is done and verified, merge
  its branch into master and delete the branch, its worktree and any stash in
  the same session. Say plainly if you stop with unmerged work. A worker may
  push the branch it owns. Pushing master, or merging into it, is the root
  agent's job and needs Lexer's explicit go-ahead.
- This repository is public. Never commit credentials, private binaries,
  proprietary game dumps or unrelated personal data.

## Checks

- Verify on CI, not on Lexer's machine. Several agents running suites at once
  pin his six-core CPU at 100%. Locally, run only the one check that covers what
  you changed, one browser at a time. For a full suite, push the branch you own
  and open a draft pull request; never merge it yourself.
- `python tools/check_plugin.py <plugin>` runs a plugin's checks and `--global`
  runs the shared ones; CI runs exactly these. New tests go in `tests/<plugin>/`
  or `tests/shared/` as `test_*.py`, `verify_*.py` or `*_check.py`, with file
  names unique across folders. Never hand-write workflows; run
  `python tools/check_plugin.py --write-workflows` after adding a plugin.
- `tools/` holds utilities people run. Checks and their helpers belong in
  `tests/`; one-off probes are deleted when their issue closes.
- No visible test windows during routine checks; headless is the default.
  Native window fixtures need Lexer's approval.

## Disk and temporary files

- The checkout holds source only. No `_scratch/`, `.pytest_cache`, `artifacts/`,
  `out/`, builds, upstream clones or browser profiles in it
  (`tests/shared/test_repo_hygiene.py` enforces this). Use your session
  scratchpad or `%TEMP%/lexeditor-dev`, and delete what you put there.
- Before a large build or download, check free space and state the cost.
- Anything the app writes to a player's disk (backups, caches, previous copies)
  needs a bound: keep the original plus the newest, or cap the size and evict.

## Editing files from a shell

- Never pass code with quotes or backslashes through a bash heredoc. Write the
  script to your scratchpad with the file-writing tool and run it.
- A patch script asserts what it expects to find before replacing it, so a
  changed file fails loudly instead of silently matching nothing.
