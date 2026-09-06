# #365 — Managed WSE2 package and Steam integration

## Request / acceptance

Verbatim user wording: [source record](../requests/wse2-managed-20260906/source.md).
(The relative link is resolved from `worklog/issues/`.) Shared checker requirements:
[#81 archive](github-81/conversation.md). Scope: bundle a fixed custom WSE2 package,
no automatic upstream updates, register main-menu pinned/installed/latest reporting,
and preserve Steam components and truthful compatibility validation.

## Implementation

`games/warband/wse2_manager.py`, root-aware plugin hooks and a physically shipped
58-file `1.1.5.1-lex1` package. The engine/Steam bytes are publisher-original; custom
packaging excludes the updater, dedicated servers and debug symbols. No engine
source rebuild is claimed. Full archive/member digests are in the runtime manifest.
Per-game-root receipts, live-process guard, cross-process install/launch locking,
verified backups, rollback and crash recovery. Launch refuses drift rather than
silently repairing or running an arbitrary helper. Stock binaries and mod files
are outside the manifest. Shared WSE2 shader/runtime destinations are backed up.

Home installs to its selected game root. Checker adds installed versions, dates
and external release-note actions, and preserves local information when upstream
fails. Only Check again refreshes cached upstream metadata; installed state stays
fresh. No checker action installs anything. Companion tests keep original
launch-window tests isolated while exercising real-bundle integrity separately.

## Evidence / delivery

Local: 28 new Python cases (2 Windows-specific skips), existing 42 Warband cases
(6 Windows-specific skips) and real Home HTML/CSS/JS rendering at 900x620 and
1440x900. Screenshot/interaction tests exercise mixed upstream failures, version
fields, external notes, Check again, Lexer Mode permission and explicit Install.
Windows CI and merge evidence are recorded in the PR; do not infer a local-PC
installation or an actual Steam session from those results.

Prepared user diagnostics: `tools/Warband-checks.cmd`; acceptance:
`docs/warband-managed-wse2.md`. The code and binary package must be merged/delivered
before marking Needs Testing. Actual Steam/Warband session acceptance remains
unverified; no achievement is forcibly unlocked or reset by tests.
