# #34: Use mouse Back/Forward for editor history

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/34)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes.
Use the current issue, relevant central Worklog/Codex material, and available
chat/file context; do not recreate a local issue archive.

The mouse's Back and Forward buttons move through the destinations the player
visited inside the editor. They are not the browser's URL history: an editor
tab is not a page, and the WebView's own history holds the chooser URL, so
stepping into it would leave the editor entirely.

## Prior failure classes that can recur

Each of these shipped at least once, and the contract in
`tools/verify_navigation_history_issue_34.py` exists to stop each coming back.

- **Falling through to WebView history.** `history.back()` in the page walks the
  WebView's URL stack and lands on the chooser, closing the editor the player
  was working in. No plugin history path may call `history.back`,
  `history.forward` or `history.go`.
- **Two histories drifting apart.** Undo/Redo of *edits* and Back/Forward of
  *destinations* are different stacks. Sharing one made an undo jump tabs and a
  tab change discard an edit.
- **A stale Forward branch.** Visiting a new destination after going Back must
  discard what was ahead. Keeping it let Forward walk into a destination the
  player had never chosen from there.
- **The GitHub screen outside the history.** It is a destination like any tab;
  when it was not one, Back from it did nothing.
- **The physical buttons bypassing the page.** The native host must hand
  unconsumed button 3 and 4 to the one shared entry point rather than acting on
  its own, or the two disagree about where "back" is.
- **Glyph-dependent controls.** Undo and Redo drawn as font arrows changed shape
  or vanished per theme; they use the shared SVG icon set.

## Primary evidence

- `class NavigationHistory` in `ui/framework.js` owns destination history and is
  separate from `EditHistory`.
- `this.entries.splice(this.index + 1)` discards the forward branch on a new
  destination; `async go(direction)` with `this.index + step` traverses.
- The initial entry is the live plugin destination, and the GitHub workspace
  shares the same destination space.
- `window.__lexeditorNavigateHistory` is the single entry point the native host
  calls; `installExtendedMouseHistory` forwards buttons 3 and 4 to it, and
  `installBrowserHistoryGuard` pushes a guard entry so an unconsumed WebView
  Back stays in the document and becomes `navigationHistory.go(-1)`.
- `windows_host.py` handles the `WM_XBUTTON` messages and `XBUTTON1`.

## Sanctioned path

Destination change in a plugin, or opening the shared GitHub screen, records one
entry. Back and Forward - keyboard, on-screen, or mouse buttons 3 and 4 - call
`navigationHistory.go`. Home is a separate guarded control that hands the
lifecycle back to the host, not a history step.

## Execution proof

`tools/verify_navigation_history_issue_34.py` passes, checking each failure class
above against the shipped source rather than against documentation.

## Player-visible acceptance boundary

Pressing the mouse's Back button in an editor returns to the previous tab or
screen inside that editor, and never closes it or returns to the chooser.
Forward returns, and stops being available once a new destination is chosen.
Undo and Redo continue to affect edits only.

## Next agent work

Read the live issue and comments and preserve the latest explicit human
corrections in this concise handoff. Do not create source-record, conversation,
or attachment archives.
