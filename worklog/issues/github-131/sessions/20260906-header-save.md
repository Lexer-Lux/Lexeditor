# Header Save dispatch repair — 2026-09-06

## Evidence and recurring failure classes

Read the preserved #131 request/archive and the existing sparse-save implementation. The recurring failure was a correct handler not wired into the user-facing path, followed by a misleading success message. Primary code: games/rdr2/editor.html saveAllChanges, saveCatalog, itemTagsCell. Execution proof must be a save request plus cleared pending state after success, not a button click or toast alone.

## Reproduced and repaired

The catalogStores list in saveAllChanges omitted alcoholEdits. Editing only Drunkenness made the actual header Save button display “All changes saved to mod files” without calling /api/alcohol-strengths/save; the edit stayed pending. An offline Chromium render using the complete production HTML/CSS/JS reproduced this. The newly added Node regression also failed before the change (zero requests, expected one).

Added alcoholEdits to that existing dispatch list. No other application code changed in this repair. The same Node regression then passed. Its second case rejects the CSV save and checks that pending edits remain, later catalog writes stop, and global success is not reported.

## Verification

- Existing 22 Python regressions and four production boot/dataset-switch Node cases passed again locally.
- Two new tests execute the actual production saveAllChanges and saveCatalog functions.
- Three offline Chromium cases execute the actual rendered controls: successful sparse save, rejected save, unavailable baseline. All passed with no page errors.
- The rendered fixture deliberately supplied stale flattened entries equal to 1. The Brandy field still showed baseline 0.17, while the explicit Moonshine override stayed 1. Saving Brandy 0.23 posted only that drink and preserved Moonshine. This tests display isolation, not the historical all-ones symptom on the user's real data.
- Screenshots were captured and the saved-value image was inspected. Native fonts, game assets, HTTP navigation/history and the WebView2 host were not tested. The fixture runs entirely offline using about:blank and synthetic API responses; it does not bypass browser navigation policy.

## Acceptance boundary

This establishes the missing Save dispatch and synthetic UI behavior. The user's selected project/CSV and installed Windows editor still require confirmation. The issue is not closed; previous handoffs and the original request are retained. The pre-update PR summary is preserved in ../sources/pr364-before-save-dispatch.json before correcting its obsolete build/verification status.
