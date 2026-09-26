---
name: knowledge
description: Where Lexeditor game knowledge lives. Use before writing or reorganising codex/ pages, and before importing notes from or retiring stores in a standalone Lexers-Mod-* repository.
---

# Codex, worklogs and standalone repositories

- Lexeditor owns the canonical game knowledge under `codex/<game>/`, with
  shared editor knowledge in `codex/shared/`. Write a page only for something
  proven and expensive to rediscover: settled mechanics, schemas, paths and
  demonstrated limits. No placeholder pages.
- Attempts, guesses, progress and pending work belong in the per-issue
  `worklog/<number>.md`, not in codex (see
  `.agents/skills/github-issues/SKILL.md`).
- Parallel contributors avoid competing global files; one integrator
  reconciles shared codex indexes.
- Search these stores when needed; do not load them in full.

## Standalone `Lexers-Mod-*` repositories

- They are storage and distribution only. They never keep their own codex,
  worklog, project memory or issue history, and their `AGENTS.md` sends
  development back here.
- When importing from one, bring only real game-development notes that are not
  already here. Never import issue mirrors, attachment caches, API snapshots or
  forwarding stubs.
- Before retiring a legacy store there, confirm its useful knowledge is
  accounted for here, then remove it and keep only the storage-only `AGENTS.md`.
- Review private-source notes before publishing them here: no credentials,
  private binaries, proprietary game dumps or unrelated personal data.
