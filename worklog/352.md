# #352: Install and launch on Windows, macOS and Linux (parent)

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/352)

## Requirements and decisions

Read the live issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-23 misc-fixes triage

Stays actionable as the parent traceability record. Agent-verifiable slice is green: tests/test_distribution_hygiene.py passes (bundled helpers pinned, private helpers/builds/profiles excluded). Remaining agent work is release-time (re-run build against the release commit, attach installers). Children #494/#495/#496 moved to waiting (need a release cut plus their OS/hardware). Human install/launch acceptance stays with Lexer at release time.

## 2026-09-23 per-game-global pass

Re-verified post-rename: tests/test_distribution_hygiene.py passes, along
with the reshade, plugin-descriptor and mod-library suites; the distribution
file list in tools/build_distribution.py was updated to the new
shaders/*.fx paths. No code beyond the 505 rename. Everything remaining is
the release-time build plus Lexer's install/launch acceptance on all three
platforms. Stays actionable.

## 2026-09-23 global-actionables pass (branch impl/global-actionables2)

Re-ran on current origin/master: tests/test_distribution_hygiene.py passes
(2 passed). No source changes needed: tools/build_distribution.py still
excludes private helpers/builds/profiles and pins bundled helpers. This PR
adds no new vendored helpers. Remaining work is release-time only: re-run
the distribution build against the release commit, attach the three
installers, and Lexer's install/launch acceptance on Windows, macOS, Linux
(children #494/#495/#496). Stays actionable.
