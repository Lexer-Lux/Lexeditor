# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5202953146 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/14

Created: 2026-08-20T11:38:08Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5202953146-42e90917adf3f11bb9b71071211466f7eda3df944683eb01327e65c6f1aaaecf.json).

## Request

Replace the current GitHub overlay with a shared in-editor GitHub tab.

- Put a GitHub-logo tab at the right edge of the main game tab row. Show it only for the authorized owner.
- Use `actionable`, `waiting`, and `unfeasible` as its subtabs.
- Replace `needs a human` and `test me` with one orange `waiting` workflow label. Anything that needs Lexer belongs there.
- Use the shared list-detail layout as the base and show three panels: a dense issue list, the selected issue editor, and comments.
- Keep every issue-list row on one line. Show the issue number, title, and a `!` when it has `high priority`.
- Put the issue number and editable title on one row. Do not show redundant Title or Body labels.
- Put comments in the right panel, open that panel at the newest comment, and allow the owner to post a comment.
- Add a clickable `!` priority control to the selected issue. It toggles the existing `high priority` label and updates the list immediately.
- Preserve secure GitHub CLI authentication. Do not expose tokens or open a browser.

## Acceptance

- The rightmost logo tab replaces the old top-bar GitHub button in both game shells.
- The three workflow subtabs load their matching issues.
- Issue rows remain one line and substantially denser than the old cards.
- Title/body edits, label edits, priority toggling, and new comments work inside Lexeditor.
- Comments begin at the bottom and remain there after posting.
- Returning to a game tab preserves unsaved editor work.

## issue 5202953146 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/14

Created: 2026-08-20T11:38:08Z; updated: 2026-09-06T13:06:24Z

Exact metadata: [source record](sources/issue-5202953146-269538e98cc21470be8bc3f8c3c3662a4f54813c373b7151602e681734405da7.json).

**Status: Implemented; needs your check.** The owner-only GitHub tab contains the issue list, editable issue and comments, with a ! priority toggle.

- [ ] Restart Lexeditor, open a game’s GitHub tab and switch status subtabs. Confirm issues are readable on one line and the selected issue matches GitHub.
- [ ] On #357, toggle ! on and back off. Confirm the list updates immediately and the original priority is restored.
- [ ] Open an issue with comments. Confirm the newest comment is visible, then return to the game tab without losing editor work. Report any mismatch or missing issue.

## comment 5355569257 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/14#issuecomment-5355569257

Created: 2026-08-20T12:00:06Z; updated: 2026-08-20T12:00:06Z

Exact metadata: [source record](sources/comment-5355569257-b7bc316b3d56e4ae7c818e7ea449397ac865ad850cb2e2b3b1041578acd2e320.json).

Implemented the GitHub workspace redesign.

The GitHub logo is now the rightmost game tab. It opens Actionable, Waiting, and Unfeasible subtabs over a shared resizable list-detail layout: dense one-line issues on the left, issue text and labels in the middle, and comments on the right. The selected issue has a direct `!` high-priority toggle. Comments open at the newest entry and can be posted from the bottom composer. The visible Title and Body captions are gone.

The RDR2 tracker now has one orange `waiting` state. All 159 issues that used `needs a human` or `test me` were migrated without changing open/closed state, and both old labels were removed. Warband and Lexeditor now use the same workflow labels.

The full hidden RDR2 and Warband suite passed, including priority changes, comment posting, workflow switching, dense rows, returning to the prior editor page, and unchanged live data files. Fully close and reopen Lexeditor before checking it.
