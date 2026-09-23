# #467: Shared mod import, storage, and updates

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/467)

## Requirements and decisions

Read the live issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-23 misc-fixes triage

Deliberately not started in misc-fixes/506: this is a full authorized feature (shared import/storage/update plus per-game adapters), not a small fix, and it deserves its own branch. Next slice when scheduled: shared folder/archive import scaffold with manual layout selection, beginning with FF7 Remake. Issue stays actionable.

## 2026-09-23 per-game-global pass

No new feature code: the agent-side contract is already implemented on this
branch and re-verified here. Shared core mod_library.py/managed_mods.py
(import, manual data-root selection, Documents Known-Folder resolution,
verified relocation with journal/recovery, release selection, failed-update
recovery, author exemption) plus FF7R/Chrono Trigger adapters;
`tools/verify_mod_library.py` passes post-rename (21 tests, OK) and runs in
the CI verifier sweep by glob. UI gating is explicit per-game capability
(`plugin.mods_load` via `_mod_loading_state`, "Mod management is not
supported for this game yet."), the editable-copy modal uses the issue's
wording, and the mod list shows name plus version. Remaining work is
per-game in-game acceptance with real mods (FF7 Remake first, authorized
2026-09-12): import, find, activate, launch, disable, plus relocation and
managed-update behavior in the real game. Stays actionable.

## 2026-09-23 global-actionables pass (branch impl/global-actionables2)

Re-ran on current origin/master: tools/verify_mod_library.py passes (21
tests, OK) plus tests/test_ff7r_graphics_tweaks.py (7 passed). No source
changes needed: shared import/manual data-root selection, Known-Folder
Documents resolution, verified relocation, release selection, failed-update
recovery, author exemption, and per-game gating are intact. Remaining work
is per-game in-game acceptance with real mods (FF7 Remake first): import,
find, activate, launch, disable, relocation, and managed updates in the
real game. Stays actionable.
