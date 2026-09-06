# #365 — Managed WSE2 package and Steam integration

## Request / acceptance

Verbatim user wording: [source record](../requests/wse2-managed-20260906/source.md).
Shared checker requirements: [#81 live issue](https://github.com/Lexer-Lux/Lexeditor/issues/81).
The live GitHub issue is the canonical request record. Its initial placeholder
handoff is retained verbatim in [the session archive](github-365/sessions/archive-import-handoff-80e7106.md).
Scope: bundle a fixed custom WSE2 package, no automatic upstream updates, register
main-menu pinned/installed/latest reporting, and preserve Steam components and
truthful compatibility validation.

## Implementation

`games/warband/wse2_manager.py`, root-aware plugin hooks and a physically shipped
58-file `1.1.5.1-lex1` package. The engine/Steam bytes are publisher-original; custom
packaging excludes the updater, dedicated servers and debug symbols. No engine
source rebuild is claimed. Full archive/member digests are in the runtime manifest.
Per-game-root receipts, live-process guard, cross-process install/launch locking,
verified backups, rollback and crash recovery. Launch refuses drift rather than
silently repairing or running an arbitrary helper. Stock executable/Steam DLLs and
mod files are outside the manifest. Shared WSE2 shader/runtime destinations are
backed up before replacement. Existing standalone launchers are not deleted.

Home installs to its selected game root. Checker adds installed versions, dates
and external release-note actions, and preserves local information when upstream
fails. First opening checks upstream; Check again refreshes cached upstream
metadata. Installed state stays fresh each opening. No checker action installs
anything. A project warning no longer masks the independent helper repair action.
Companion tests keep original launch-window fixtures isolated while exercising
real-bundle integrity separately.

## Verified delivery

PR #366 merged to master as `a49464326ec269d02e957e8cf6c2a89a546ac8ac`, with tested
head `daa8ff4037217d2598506f074de81019773cd3cb`. The actual 20,175,718-byte ZIP is
tracked in Git, not a deferred download or pointer. Source publication run
34045219306 verified byte-identical package reproduction and Linux regressions.
Archive SHA-256: `43dc883e0f78cd1fad49dea696080154be0b498000980f63d91e96712707cd31`.

Final [managed-helper CI](https://github.com/Lexer-Lux/Lexeditor/actions/runs/34046060075)
and [companion Warband CI](https://github.com/Lexer-Lux/Lexeditor/actions/runs/34046060066)
passed. Windows and Linux both ran Python 3.10 and 3.11: 28 new helper/package/API
cases, 42 existing Warband cases, 7 coverage cases, Node graph checks, and the
Windows one-click diagnostic. Windows-only cases skip on Linux. Home's real
HTML/CSS/JS was rendered at 900x620 and 1440x900; tests cover errors, pin/installed/
latest/date, external notes, explicit install, warning-state repair and missing
roots. Existing Warband rendered/WebGL checks also pass. Local screenshots were
inspected; these are fixture checks, not installed-game or WebView2 acceptance.

## Failures resolved during validation

Windows fixture TEMP paths used a short-name spelling while production normalized
to the full path, so injected failure hooks did not fire. Normalize the fixture
root and explicitly assert the disk-failure hook ran; rollback requirements were
not weakened. Python 3.10 CI needed the existing declared `tomli` fallback; this
is now installed in the test matrix.

The unrelated incomplete `tools/magic-rdr/source` gitlink made checkout's immediate
recursive credential cleanup fail. The read-only regression jobs use standard
checkout and remove their local auth header directly before tests; no repository
index or submodule was changed. The one-time source publication token cannot edit
workflow files; source publication excludes those edits, which were made through
the authorized GitHub connector. All temporary publication workflows/patch files
were removed; only read-only validation remains in the final diff.

## Remaining acceptance, not deferred packaging work

Update master, restart Home, close Warband/updater processes and select Warband →
Install / Repair WSE2. Prepared diagnostics: `tools/Warband-checks.cmd`. Full steps:
`docs/warband-managed-wse2.md`. Confirm installed package/version, then separately
check the real selected module, Steam overlay, playtime, used Steam features and
one normally earned eligible achievement. No forced unlock/reset is performed.

Actual installation on Lexer's PC and a real Warband/Steam session remain
unverified. A pin or passing CI must never be treated as evidence of an achievement
award. Keep the issue open for the prepared installed acceptance; a failure returns
to implementation with its runtime/module/log evidence.


