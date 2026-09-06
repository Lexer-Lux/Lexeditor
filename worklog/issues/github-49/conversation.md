# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5287107844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49

Created: 2026-08-29T14:28:15Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5287107844-d6dbeed7cc8de34ef73ee5f3ef7fd78d55ffa0c460a73af1e745acd882d4a26f.json).

## Report
After restoring the frameless Lexeditor window from its work-area maximized state, the smaller window cannot be moved or resized.

## Required behavior
- Restoring must leave the native window in a normal, movable, resizable state.
- Dragging the shared command strip must move it.
- All edge and corner handles must resize it.
- Maximizing must still preserve the Windows taskbar work area.

## Acceptance
Verify the real native window state and style after maximize -> restore, then verify that a move request and all eight resize hit-tests can change the restored window bounds.

## issue 5287107844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49

Created: 2026-08-29T14:28:15Z; updated: 2026-09-06T13:06:50Z

Exact metadata: [source record](sources/issue-5287107844-1841bf675ddd1036297e71bf2be2ef8ee4cf6e77078363f59f4beb87be0b56d9.json).

**Status: Repairs and window-state persistence are ready for review.**

- [ ] Restart Lexeditor, maximize it, then drag the top strip. It should remain maximized and respect the taskbar area.
- [ ] Restore the window. Drag the top strip and each edge/corner; all should move or resize normally.
- [ ] Close and reopen once while restored, then once while maximized. Confirm position, size and maximized state return correctly. Report the transition that fails.

## issue 5287107844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49

Created: 2026-08-29T14:28:15Z; updated: 2026-09-06T13:06:50Z

Exact metadata: [source record](sources/issue-5287107844-eb0dd0301834a7f9f67fcf13db17177d97bfb02f9ee74303db5adce80cf6d477.json).

**Status: Repairs and window-state persistence are ready for review.**

- [ ] Restart Lexeditor, maximize it, then drag the top strip. It should remain maximized and respect the taskbar area.
- [ ] Restore the window. Drag the top strip and each edge/corner; all should move or resize normally.
- [ ] Close and reopen once while restored, then once while maximized. Confirm position, size and maximized state return correctly. Report the transition that fails.

## comment 5462995958 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49#issuecomment-5462995958

Created: 2026-08-29T14:34:47Z; updated: 2026-08-29T14:34:47Z

Exact metadata: [source record](sources/comment-5462995958-a694e248145b2cde8e4547aba2077734d42fd0dcfd583c389d14fb227f238514.json).

The resize elements existed, but the borderless native window could reject their old border command. Resizing now tracks the real Windows cursor and changes the native bounds directly; the command strip now uses the host-supported drag region. The hidden native test passed maximize, restore, and all eight resize directions. Please restart Lexeditor, restore it from maximized, then drag the top strip and test one edge and one corner.

## comment 5464177803 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49#issuecomment-5464177803

Created: 2026-08-29T18:40:57Z; updated: 2026-08-29T18:40:57Z

Exact metadata: [source record](sources/comment-5464177803-6944f8894021b8cf659a58db89a331ff4493a1dc5c4e6bcefcc950e0e2d31416.json).

The maximized strip still had pywebview's native drag-region marker, so Windows treated a drag as restore-and-move even though the resize handles were disabled. Maximized state now removes that marker, and the host also rejects direct move and resize requests. The hidden real WebView2 test kept the maximized bounds unchanged, then restored normal dragging and all eight resize directions. Restart Lexeditor, maximize it, and drag the top strip; it should remain fixed.

## comment 5473982806 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/49#issuecomment-5473982806

Created: 2026-08-31T05:06:11Z; updated: 2026-08-31T05:06:11Z

Exact metadata: [source record](sources/comment-5473982806-4efe2a6901b5df86f7ab94601ff7b21aa1393ed5c6eaac8d4c5ebde91dcdfb9b.json).

Lexeditor now saves the restored window rectangle and maximized state on close or restart, then restores both on the next launch. Saved bounds are clamped to the nearest monitor work area so a display change cannot reopen the app off-screen. The persistence and invalid-state contracts pass; please restart once after maximizing to confirm the visible native window returns maximized.
