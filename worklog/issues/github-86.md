# #86: Centralize all game codices and per-issue worklogs (DEFERRED)

[Live GitHub issue](https://github.com/Lexer-Lux/Lexeditor/issues/86)
Full deferred specification and preserved request: [deferred-consolidation-spec.md](github-86/deferred-consolidation-spec.md)

## Status decision

Consolidation is DEFERRED at Lexer's request ("We should do that later").
No migration, comment cleanup, archive deletion, branch merging, or cleanup-job
restart begins in this change. Stays `actionable` (not `waiting`): deferred
agent work, no action needed from Lexer. Labels stay
`actionable` + `documentation` + `global`.

## Requirements and decisions

The deferred spec in `worklog/issues/github-86/deferred-consolidation-spec.md`
is authoritative; the earlier issue bodies and the verbatim scheduling quote it
preserves remain the requirement source. In short: one settled codex per game
under `codex/<game>/` (shared editor knowledge under `codex/shared/`), one
active internal worklog per issue with full requirements/decisions/evidence,
verbatim preservation of Lexer's requests and attachments, brief GitHub bodies,
verified comment archiving before any deletion, post-merge reconciliation, and
private-source review before publishing.

## Current implementation and evidence

- `codex/<game>/README.md` routing pages and the `codex/README.md` index exist;
  `tools/import_knowledge.py` provides import/index scaffolding. None of this
  counts as completed migration per the spec's acceptance boundary.
- Per-issue archive for #86 is preserved under `worklog/issues/github-86/`
  (`sources/`, `conversation.md`, `deferred-consolidation-spec.md`); this stub
  previously told agents not to create source archives, which contradicted the
  preserved archive — corrected here to point at it instead.
- Live GitHub issue body already carries the deferred-status banner and links
  to the spec; labels verified as `actionable`, `documentation`, `global`.
- Triage comment confirms: no migration work starts; stays actionable.

## Next agent work (on resume only)

Follow `deferred-consolidation-spec.md`: auditable source inventory, populate
per-game codices, substantive per-issue worklogs, verified comment archiving,
incremental catch-up after parallel merges, explicit gaps. Do NOT start any of
that until Lexer lifts the deferral.
