# Central game knowledge

Lexeditor is the **only canonical development home** for game mechanics, formats, proven engine limits, editor knowledge, research notes and maintained Codex material. Full requests, attempts, test evidence and discussion belong in the matching per-issue Worklog rather than being duplicated into Codex pages.

## Game indexes

- [Bannerlord](bannerlord/README.md)
- [Final Fantasy VII](ff7/README.md)
- [Final Fantasy VIII](ff8/README.md)
- [Final Fantasy IX](ff9/README.md)
- [Red Dead Redemption](rdr1/README.md)
- [Red Dead Redemption 2](rdr2/README.md)
- [Termina](termina/README.md)
- [Warband](warband/README.md)
- [Shared Lexeditor knowledge](shared/README.md)

## Organization rules

Game folders contain durable, reconciled knowledge. Focused top-level documents such as `ff7-data.md`, `ff8-*.md` and `ff9-memoria-integration.md` are retained when they are useful implementation references; their game's README is the stable entry point.

Imported historical claims must be reconciled when newer code, tests or player evidence differs. Migration provenance and explicit gaps live in `worklog/migrations/game-knowledge.json` and `worklog/migrations/1.1-game-knowledge.md`.

The standalone `Lexers-Mod-For-*` repositories are **distribution/storage mirrors, not knowledge stores**. Do not create or recreate Codex, Worklog, project-memory or issue-history files there. Agents looking for historical material should come back to this repository instead.
