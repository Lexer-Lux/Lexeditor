# Central Worklog

Lexeditor is the canonical home for development handoffs across every supported game and Lexer mod. GitHub issues and their comments remain the canonical request/discussion record; the Worklog records implementation state, tests, decisions, and next work without mirroring GitHub itself. Durable game knowledge belongs in `codex/`.

## Layout

- `issues/github-N.md` — current implementation handoff for Lexeditor issue N when internal continuity is useful.
- `requests/` — project/task notes that are not copies of GitHub issue bodies or comments.
- `imports/` — useful historical development notes migrated from standalone mod repositories. Do not import issue mirrors, attachment caches, or generated GitHub API snapshots.
- `migrations/` — migration manifests and consolidation notes that do not duplicate issue contents.
- `legacy/` — older development notes retained for reference but not treated as current status.
- `issue-status-audit/` — status-maintenance plans/evidence, not an archive of the issues and not implementation truth by itself.

## Rules for agents

1. Read the live GitHub issue and comments for the request. Do not archive them into the repository.
2. Never create `worklog/attachments/`, `issues/github-N/sources/`, `issues/github-N/conversation.md`, or any equivalent issue/comment/attachment mirror.
3. Do not download GitHub issue screenshots or other attachments merely for archival or provenance. Purposeful project assets belong in their actual project asset paths.
4. Never delete issue comments as part of Worklog/Codex cleanup or synchronization.
5. Put new implementation history under the relevant central Lexeditor issue handoff or project note. Keep it concise and current.
6. Do not create new Codex/Worklog/project-memory stores in any `Lexers-Mod-For-*` repository. Those repositories are finalized-mod storage/distribution mirrors only.
7. When runtime work happens in a standalone mod repository for packaging reasons, bring the meaningful implementation result back to Lexeditor before considering the handoff complete; do not bring back a second issue archive.
8. Preserve genuinely useful imported development knowledge under `imports/`, but never treat forwarding stubs, generated snapshots, issue exports, or attachment caches as knowledge that needs preserving.
9. Issue labels/bodies/comments on GitHub are the current task state. A Worklog can explain that state but must not be used to pretend an untested candidate was accepted.

See `migrations/game-knowledge.json` and `migrations/1.1-game-knowledge.md` for the consolidation provenance used by release 1.1.
