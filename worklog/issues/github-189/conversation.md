# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356304202 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/189

Created: 2026-08-06T04:21:39Z; updated: 2026-09-05T06:59:34Z

Exact metadata: [source record](sources/issue-5356304202-a29d720a79d0aae7ec5b72ef021883e066a412490f84ed1128aa65ea9dd2a83b.json).

## Goal

Make parallel worktree agents stop competing over the same knowledge files and output binary.

## Design

- Split settled project knowledge into topic-owned files under `codex/`; keep `CODEX.txt` as a generated compatibility index.
- Split attempt history into one file per GitHub issue under `worklog/issues/`; preserve old mixed/session material under `worklog/legacy/`; keep `Worklog.txt` as a generated compatibility index.
- Worktree agents edit only their topic module, relevant data, and their own issue worklog. They do not build or install `GameplayTweaks.asi`.
- One integration agent owns shared registries/dispatchers, merges work, rebuilds generated indexes, runs the full build, installs the single ASI, and updates GitHub state.
- GitHub issues are the only live tracker. `TODO.txt` is deprecated archival material and has no validator or hooks.

## Acceptance

- [x] Existing CODEX and Worklog content is migrated without deletion.
- [x] Search/index tooling finds migrated material by topic and issue.
- [x] AGENTS.md defines worktree-agent versus integration-agent ownership.
- [x] Knowledge index validation passes: 10 codex topics and 77 worklog files.
- [x] Obsolete `check_todo.py`, TODO edit hook, and TODO pre-commit hook are removed.
- [x] No ASI build is required for this documentation/workflow-only change.
- [x] Commit the modular source and swarm foundation so newly created Git worktrees inherit it.

## Completion

Committed locally on `master` as `cdd4359` (`Checkpoint all current RDR2 overhaul work`). The primary working tree is clean and local worktree agents can now branch from the conflict-safe foundation. The commit has not yet been pushed.

## issue 5356304202 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/189

Created: 2026-08-06T04:21:39Z; updated: 2026-09-06T13:17:27Z

Exact metadata: [source record](sources/issue-5356304202-f2c8bad19f6c71dbb9ded1c318097171dbf424fe09c635f9ff9d1eb7f171071a.json).

**Status: Closed workflow change.** Topic-owned research and per-issue worklogs separate technical evidence from the brief GitHub issues humans read. Independent workers own their modules; one integrator owns shared build/install output. The old instruction to use issue bodies as the only development tracker is superseded.
