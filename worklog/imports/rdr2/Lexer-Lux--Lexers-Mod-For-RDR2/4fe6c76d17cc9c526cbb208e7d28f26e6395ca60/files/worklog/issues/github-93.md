# Worklog: GitHub 93

## GitHub #93 conflict-safe agent swarm workflow — 2026-08-05

Migrated settled knowledge from one shared `CODEX.txt` into ten topic-owned
files under `codex/`. Migrated 96 historical Worklog sections into 76 owned
files: single-issue histories under `worklog/issues/`, mixed and session history
under `worklog/legacy/`. The source hashes and every migrated section hash are
recorded in `worklog/migration-manifest.json`.

`CODEX.txt` and `Worklog.txt` became generated compatibility/search indexes.
`tools/knowledge_files.py` owns one-time migration, deterministic index rebuild,
and validation. AGENTS now assigns feature worktree agents only topic/issue
files, prohibits them from building or installing the shared ASI, and reserves
merge, shared registries, full validation, build, install, and final GitHub state
for one integration agent.

Removed the obsolete `TODO.txt` validator, its Claude edit hook, and the local
pre-commit hook that ran it. `AGENTS.md` now identifies GitHub issues as the
only live tracker and treats `TODO.txt` as read-only deprecated archival material.
