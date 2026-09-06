# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356331270 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/289

Created: 2026-08-17T03:24:07Z; updated: 2026-09-05T07:05:04Z

Exact metadata: [source record](sources/issue-5356331270-c63df40355192ca93bb3788fc372e080fa71729232d77be8913abf827c16808a.json).

## Requested behavior

Each game editor has an owner-only GitHub logo in the shared top bar. The control is not on the main menu.

- Show the control only when GitHub CLI reports an allowed active owner account for that plugin.
- Select the control to replace the normal editor content with an in-app GitHub issue workspace.
- Select it again to return to the exact editor page and state that was open.
- List the plugin repository's issues inside Lexeditor.
- Open an issue inside Lexeditor and show its title, state, labels, body, and comments.
- Let the owner add and remove existing repository labels inside Lexeditor.
- Keep GitHub credentials in GitHub CLI. Lexeditor must not read, display, or store the token.
- Do not launch the browser for this workflow.
- Keep normal users and plugins without a configured repository free of GitHub controls.

## Acceptance

- The GitHub logo is visible in the RDR2 and Warband editor top bars for the authorized active account.
- The main-menu game cards have no GitHub button.
- The issue list, issue details, and label changes work inside the single Lexeditor WebView2 window.
- Toggling the logo returns to the prior game page without discarding unsaved edits.
- An unauthorized or logged-out session receives no owner UI and cannot use the bridge methods.


## issue 5356331270 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/289

Created: 2026-08-17T03:24:07Z; updated: 2026-09-06T13:18:55Z

Exact metadata: [source record](sources/issue-5356331270-2a441e209517a56c01766d56d7de934fb31da3e744522efa221ed426006182bc.json).

**Status: Closed for the initial integration.** Authorized owners can read and edit issues inside the existing window and return without losing editor work. Credentials stay with GitHub CLI. The later three-panel workspace and status organization are tracked in #14.

## comment 5550164379 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/289#issuecomment-5550164379

Created: 2026-08-17T03:43:43Z; updated: 2026-08-17T03:43:43Z

Exact metadata: [source record](sources/comment-5550164379-1f5bca03eb16ba91574e69c0751699d97db7be7ea9562cb6d7814e244a4a14eb.json).

The GitHub control is now inside each active game editor, not on the main menu. It is a GitHub logo beside Data Map and appears only for the allowed active GitHub CLI owner.

Selecting it opens an embedded issue workspace in the same Lexeditor window. It lists open, closed, or all issues; shows issue text, labels, and comments; edits the title and body; and adds or removes repository labels. It never opens a browser. Select the logo again to return to the same game tab with filters and unsaved edits intact.

Automated owner/denial checks passed. Headless renders passed in the real RDR2 and Warband shells, including an RDR2 dirty edit that survived opening and closing GitHub. Fully close and reopen Lexeditor once because an already-running process still has the old desktop bridge loaded.

