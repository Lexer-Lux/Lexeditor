# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5285953301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25

Created: 2026-08-29T10:18:21Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5285953301-e1a53e4910e86c21dbcc2a574c9851b3e1ab453f60c2c3be2feb8d672e6a7c83.json).

Create one shared presentation contract for all game plugins.

Requested behavior:
- Sort normal game tabs alphabetically.
- Keep Settings last among the text tabs and give it a distinct shade.
- Put each record ID on the same title row as the record name, right-aligned and in the same title color. Do not repeat labels such as `Character ID` or `Item ID` below the title.
- Fit list rows to the available height. Never show a clipped final row or a master-list scrollbar in a paged list-detail view.
- Remove toolbar totals such as `24706 items` when a pager exists.
- Put `X-Y of Z records` on the right side of the full-width bottom pager. Use the view's real record noun, such as items, effects, or tables.

This is a shared framework requirement. Plugins must provide only their record noun and view-specific columns; they must not rebuild the pager or title contract.

## issue 5285953301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25

Created: 2026-08-29T10:18:21Z; updated: 2026-09-06T13:06:33Z

Exact metadata: [source record](sources/issue-5285953301-0a9bbc845d62be6c25d99e83a974920ce567e52d9b54aeb8920a8bea1f819dad.json).

**Status: Implemented; needs your visual check.** Normal tabs are alphabetical; Tweaks is last and distinct. Record IDs belong with names, and paged lists show complete rows with one total.

- [ ] Open Blank’s 2 Panels page, then RDR2 Items. Resize the window and page through records: no partial bottom row or vertical list scrollbar should appear.
- [ ] Check the record heading and bottom range/total; neither identity nor totals should be duplicated. Confirm Tweaks stays last. Report the view and screenshot of any mismatch.

## issue 5285953301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25

Created: 2026-08-29T10:18:21Z; updated: 2026-09-06T13:06:33Z

Exact metadata: [source record](sources/issue-5285953301-d4bb523a18ecac054cfe7a8df138e47fa81656b0ace4700ef37b6b83892599a4.json).

**Status: Implemented; needs your visual check.** Normal tabs are alphabetical; Tweaks is last and distinct. Record IDs belong with names, and paged lists show complete rows with one total.

- [ ] Open Blank’s 2 Panels page, then RDR2 Items. Resize the window and page through records: no partial bottom row or vertical list scrollbar should appear.
- [ ] Check the record heading and bottom range/total; neither identity nor totals should be duplicated. Confirm Tweaks stays last. Report the view and screenshot of any mismatch.

## comment 5461866419 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5461866419

Created: 2026-08-29T10:42:50Z; updated: 2026-08-29T10:42:50Z

Exact metadata: [source record](sources/comment-5461866419-bffceff54ecbedb6269f3aedae30037c890674321dbc30c013af93e5541cfd17.json).

The shared shell now sorts normal tabs alphabetically and keeps Settings last with a separate shade. The shared pager owns the record total as X-Y of Z, and the fitted-list repair counts column headers after the game font loads, which removes clipped rows and the page-size oscillation. The rendered FF8 Items view fits 16 complete rows with no list scrollbar.

## comment 5464135385 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5464135385

Created: 2026-08-29T18:32:02Z; updated: 2026-08-29T18:32:02Z

Exact metadata: [source record](sources/comment-5464135385-fd39cf5ade87a9cb1f928c0a05f2e018cc05caed1373e20867105bae042824c1.json).

Fixed the covered panel edge. The layout had reserved a hard-coded 52 pixels, but FF8's rendered pager is 58 pixels tall. The shared view now measures and reserves the actual pager height; one-page views reserve nothing. At 1280×720 and 1600×900, both panels now end above the pager with no overlap.

## comment 5464157265 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5464157265

Created: 2026-08-29T18:36:25Z; updated: 2026-08-29T18:36:25Z

Exact metadata: [source record](sources/comment-5464157265-de9ac93410aae28a9643680d28d78247bd1ec1744c56e91188c0eb44e08d19b6.json).

Refined the pane fit to match the FF8 window style. The shared fitter now measures the header, complete rows, and panel borders, then gives the Table, Detail, and divider that same exact height. The partial-row remainder is black instead of gray; the fixed pager remains silver through the bottom edge. One- and three-barrel renders passed at 1280×720 and 1600×900.

## comment 5471754684 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5471754684

Created: 2026-08-30T22:51:20Z; updated: 2026-08-30T22:51:20Z

Exact metadata: [source record](sources/comment-5471754684-b12cc12208cbc30c77f147d0bbe18ba1815d776855ceda7cbd9729decbabae84.json).

Naming clarification: keep the shared application dialog as Lexeditor Settings and plugin configuration as plugin settings, but label pages that edit in-game patch/mod behavior as Tweaks. The shared special-tab ordering must recognize Tweaks as the final distinct text tab.

## comment 5471818129 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5471818129

Created: 2026-08-30T23:05:24Z; updated: 2026-08-30T23:05:24Z

Exact metadata: [source record](sources/comment-5471818129-7fcd5e33ebaf75f96e1ddbe17eea47309ed5a854cd70678f8a7bf6ea44914954.json).

The in-game patch/configuration pages are now labeled Tweaks in FF8, Warband, RDR, and RDR2. Internal routes remain stable, and the shared ordering contract still keeps that special page last. Lexeditor Settings keeps its own name.

## comment 5473538323 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/25#issuecomment-5473538323

Created: 2026-08-31T04:03:31Z; updated: 2026-08-31T04:03:31Z

Exact metadata: [source record](sources/comment-5473538323-a309bebf62835e40497c1e543cb523850a152fac51abd9c90a02e75715788577.json).

Blank's 2 Panels page now uses the shared paged list-detail view with 48 records, search, four pages, fitted rows, and stable sorting and selection.
