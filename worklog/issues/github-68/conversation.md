# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5294730280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68

Created: 2026-08-30T22:32:47Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5294730280-ae18cee21081d29d066a95b9083291e2ce9b177bed8292bfedfdb31cd7056914.json).

# Goal

Use one shared settings-save control in the global Lexeditor settings dialog and every plugin Settings page.

# Required behavior

- Replace textual Save buttons and settings-specific save notices with the same floppy-disk control used by the plugin command row.
- Use the active plugin theme, dimensions, icon, disabled treatment, busy throbber, and unsaved-change badge.
- Keep the settings control gray and disabled when its own settings scope has no changes.
- Show only the number of unsaved settings changes in its badge. Do not include edits from Items, Shops, or another game-data page.
- Left-click saves only that settings scope.
- Right-click opens the normal discard confirmation and restores only that settings scope to its last saved state.
- Keep the command-row save control independent. It continues to track all unsaved plugin changes.

# Shared design

The UI framework owns one reusable settings-save control. Plugins provide only their settings dirty count, save operation, and restore operation.

# Acceptance

- Global settings start with a disabled floppy. One changed setting enables it and shows badge 1. Saving clears and disables it. Right-clicking after another edit confirms and restores the saved value.
- FF8, Warband, RDR, and RDR2 Settings pages use the shared control and count only their setting edits.
- Saving or discarding settings does not save or discard unrelated plugin data.
- The control renders with each plugin theme and matches the command-row save control.


## issue 5294730280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68

Created: 2026-08-30T22:32:47Z; updated: 2026-09-06T13:06:56Z

Exact metadata: [source record](sources/issue-5294730280-cae628efd5aee690eb0a4c5ed5b64aff58bb67da63646f6d4cf888025b255cd9.json).

**Status: Implemented; latest save-dialog repairs need your check.** The settings floppy tracks only settings changes. Successful saves close the dialog; dirty dismissal must not silently discard work.

- [ ] Restart Lexeditor. Change one setting: confirm badge 1. Save, reopen and confirm the value persisted and the badge cleared.
- [ ] Change it again, right-click the floppy and confirm discard: the saved value should return.
- [ ] Leave a disposable item edit unsaved, then save/discard a setting. Confirm the item edit remains unsaved. Check that cancelling a dirty dialog close keeps its draft; report any lost edit or failed save.

## comment 5471736015 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5471736015

Created: 2026-08-30T22:47:14Z; updated: 2026-08-30T22:47:14Z

Exact metadata: [source record](sources/comment-5471736015-5ac53da47244590df5b2adb5b91f361649795869e7731de0af3f3ac3ea1e21f4.json).

Global settings and all four plugin settings pages now use the shared floppy control. Each page keeps its own settings-only dirty count, badge, save action, and confirmed right-click discard; it does not consume or discard game-data edits. Hidden global and FF8 renders passed both save and discard paths.

## comment 5472349103 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5472349103

Created: 2026-08-31T00:47:56Z; updated: 2026-08-31T00:47:56Z

Exact metadata: [source record](sources/comment-5472349103-fe147241bf121175f2d721471b954d811ba0a6101fe129bd82806dd27c2efd84.json).

Settings now stays open when the backdrop is clicked. Escape and the close button use the same guarded close path: Cancel keeps the draft, and confirmed discard restores the saved snapshot before closing. The three-lane layout compacts before it scrolls. A 1440 x 900 render fits without a scrollbar; a 1440 x 600 render adds one because the content cannot fit. Please check editing a setting, clicking outside, and using Close or Escape.

## comment 5472415770 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5472415770

Created: 2026-08-31T00:59:51Z; updated: 2026-08-31T00:59:51Z

Exact metadata: [source record](sources/comment-5472415770-83e18cc6c91b08e7823cc2d9a6a9e391d8d57a98cf3e01ccff18d235e76b358f.json).

Repaired the shared current/default Settings pair. Number and select controls can now shrink inside their own half of the row, and percentage fields use the short % suffix while the description carries the full meaning. Neutral and FF8-themed renders showed no overlap or horizontal overflow, including Main menu height and its EVERYONE default.

## comment 5472579770 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5472579770

Created: 2026-08-31T01:27:25Z; updated: 2026-08-31T01:27:25Z

Exact metadata: [source record](sources/comment-5472579770-50c541ababfe00a5391283dc42b49abc7810494e51c796fd8d5fc87def324465.json).

Clean Settings dialogs now close when you click outside. Dirty dialogs remain protected until Save succeeds or discard is confirmed. The UI now sends one named settings object to the host, so adding another setting cannot reproduce the positional-argument mismatch. The old positional form remains supported for an already-running older page. Your restart confirms the reported save break was the stale-process case.

## comment 5474682251 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5474682251

Created: 2026-08-31T06:36:34Z; updated: 2026-08-31T06:36:34Z

Exact metadata: [source record](sources/comment-5474682251-ed13a20eb50f5731768b118c75a6a3f0a684b38c3a1ebce81f2b5b09f18191ac.json).

Fixed the settings save failure caused by a new UI running against an older resident host. The dialog now sends only the current/default keys that the host advertises. A newly added unsupported control stays visible but disabled and asks for a restart; it can no longer block every other setting from saving. A rendered old-host simulation rejected unknown keys, saved Searcher hold time successfully, and confirmed loadingTransitionMinimumSeconds was omitted. Current-host settings checks also pass.

## comment 5474703465 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5474703465

Created: 2026-08-31T06:38:58Z; updated: 2026-08-31T06:38:58Z

Exact metadata: [source record](sources/comment-5474703465-5107b8d0ccf407cb609437a394819ecd9a27f92ee90591e55b4985920ae3fd5d.json).

Removed the redundant Managed helpers block from global Settings. FFNx is FF8-specific, and FF8 Info already shows its installed state, version, readiness message, and latest result. The global settings host also no longer queries FFNx while Blank or another plugin is active. Rendered Settings and FF8 Info checks pass.

## comment 5482423854 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/68#issuecomment-5482423854

Created: 2026-08-31T18:05:02Z; updated: 2026-08-31T18:05:02Z

Exact metadata: [source record](sources/comment-5482423854-391d04fdcac2f13f01397f6512d1294d400da8cee4d8cbb1687b12a1a9e5e18a.json).

A successful global or plugin Settings save now closes the dialog after the host confirms the write. The rendered test changed three settings, showed badge 3, saved once, closed the dialog, and confirmed the saved values; the independent command-row save state is unchanged.
