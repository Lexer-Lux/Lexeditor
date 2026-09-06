# Central Worklog

Lexeditor is the canonical home for development history across every supported game and Lexer mod. Worklogs preserve what was requested, attempted, tested, rejected, merged and still needs acceptance. They are historical evidence; durable game knowledge should be distilled into `codex/` rather than rewritten here.

## Layout

- `issues/github-N/` or `issues/github-N.md` — canonical history for Lexeditor issue N, including imported runtime-repository sessions when relevant.
- `requests/` — verbatim or normalized request captures used by multi-issue work.
- `attachments/` — retained reports, snapshots and supporting artifacts that belong to current Lexeditor work.
- `imports/` — verbatim historical material migrated from standalone repositories. Paths include the source repository and source revision so newer evidence never silently overwrites history.
- `migrations/` — migration manifests, provenance and consolidation notes.
- `legacy/` — older material retained for reference but not treated as current status.
- `issue-status-audit/` — status-maintenance evidence, not implementation truth by itself.

## Rules for agents

1. Put new development history here, under the relevant central Lexeditor issue or request.
2. Do not create new Codex/Worklog/project-memory stores in any `Lexers-Mod-For-*` repository. Those repositories are finalized-mod storage mirrors only.
3. When runtime work happens in a separate mod repository for packaging reasons, bring its meaningful session evidence back into the matching Lexeditor issue Worklog before considering the handoff complete.
4. Preserve imported history verbatim under `imports/`; add newer conclusions separately instead of rewriting old claims.
5. Issue labels/bodies on GitHub are the current task state. A Worklog can explain that state but must not be used to pretend an untested candidate was accepted.

See `migrations/game-knowledge.json` and `migrations/1.1-game-knowledge.md` for the consolidation provenance used by release 1.1.
