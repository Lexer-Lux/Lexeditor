# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5285751312 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22

Created: 2026-08-29T09:29:50Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5285751312-540e8b4db1cb9401df902ef9aa3652bdfb9941e4519da6289067dc26940d5d13.json).

Replace the wide main-menu game cards with vertical game-box-art tiles.

Requested behavior:
- Use cached game box art, preferably from the game's Steam library artwork when a Steam app ID exists.
- Keep a neutral fallback when artwork is unavailable or the app is offline.
- Show one status icon in a tile corner: Added, Warning, Not added, or Scanning.
- Remove the duplicate visible `Ready`/`Added` success messages.
- Move the game path, scan detail, problems, and other secondary information into a hover/focus panel.
- Do not show a font control for games that declare no downloadable fonts.
- For games with declared fonts, the hover must name every font and show a check or X for its installed state. Clicking the font control still downloads missing fonts; errors stay visible.
- Preserve keyboard access, click behavior, automatic scan updates, sorting, and the existing locate/open dialogs.

Acceptance:
- A rendered main menu shows vertical box-art tiles at normal desktop size.
- Added/Warning/Not added/Scanning each have one unambiguous corner indicator.
- Fontless games have no font control.
- A font-enabled game lists each configured font with its correct installed state on hover/focus.
- The menu remains usable without network access or downloaded artwork.

## issue 5285751312 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22

Created: 2026-08-29T09:29:50Z; updated: 2026-09-06T13:06:28Z

Exact metadata: [source record](sources/issue-5285751312-3932a40daac853dd69f4ff21c3db6735b101600afdc2780b0b61b99c11ea587c.json).

**Status: Implemented; needs your visual check.** Home uses uncropped box art, Ready/Broken/Absent states, hover details and automatic game discovery. Later title positioning and window-button repairs are included.

- [ ] Restart Lexeditor. Hover or keyboard-focus an installed and an absent game: check the name above the cover, action, status and path; only absent art should be desaturated.
- [ ] Check folder/version controls, font details where offered, and the bottom-left social buttons. Confirm nothing overlaps at your normal window size.
- [ ] Confirm minimize, maximize and close are visible bordered buttons. Report any wrong state, missing art or clipping.

## issue 5285751312 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22

Created: 2026-08-29T09:29:50Z; updated: 2026-09-06T13:06:28Z

Exact metadata: [source record](sources/issue-5285751312-aed147de97446da45dc38b7a5ade410d340dea1a27e2ee9ac65d2e4932d80f62.json).

**Status: Implemented; needs your visual check.** Home uses uncropped box art, Ready/Broken/Absent states, hover details and automatic game discovery. Later title positioning and window-button repairs are included.

- [ ] Restart Lexeditor. Hover or keyboard-focus an installed and an absent game: check the name above the cover, action, status and path; only absent art should be desaturated.
- [ ] Check folder/version controls, font details where offered, and the bottom-left social buttons. Confirm nothing overlaps at your normal window size.
- [ ] Confirm minimize, maximize and close are visible bordered buttons. Report any wrong state, missing art or clipping.

## comment 5461597518 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5461597518

Created: 2026-08-29T09:39:11Z; updated: 2026-08-29T09:39:11Z

Exact metadata: [source record](sources/comment-5461597518-ccc57636fea85d651fd75895720f5c6861098b1ef1698b828d2fe53b35f193fd.json).

Replaced the wide cards with portrait Steam box-art tiles. Each game now has one corner status icon; the duplicate Added/Ready text is gone. Hover or keyboard focus shows the path, scan state, problems, and action. Font controls now appear only for games that declare fonts, and their hover lists each font by name with a check or X. Artwork is cached privately and the neutral fallback works offline. Restart LEXEDITOR and inspect the main menu.

## comment 5461865982 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5461865982

Created: 2026-08-29T10:42:45Z; updated: 2026-08-29T10:42:45Z

Exact metadata: [source record](sources/comment-5461865982-60210ee3965cd5a37ee23723e628fb8764434686dca562d41f11b5d8f0ece15d.json).

The box-art tile now keeps the game name and font details hidden until hover or keyboard focus. Games with no declared fonts show no font control; declared fonts are listed by name with their installed state.

## comment 5462005407 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5462005407

Created: 2026-08-29T11:11:27Z; updated: 2026-08-29T11:11:27Z

Exact metadata: [source record](sources/comment-5462005407-73e0f1c3af9bfcdcc77afe760aa2b6a3a763921480692e63132c1c42e0629b57.json).

The scan refresh was rebuilding every box-art card every 350 ms. That restarted the throbber and replayed the hover reveal. It now updates the existing card in place. A rendered polling test kept the same card and throbber nodes, kept the hover open, changed the progress text, and confirmed that the animation clock continued.

## comment 5464680015 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5464680015

Created: 2026-08-29T20:21:02Z; updated: 2026-08-29T20:21:02Z

Exact metadata: [source record](sources/comment-5464680015-8a01962ac19d088e03a8fc8ef0e78e5fa3d97817c8b2546752acc57adbd4bdcc.json).

Refine the box-art menu: use uncropped square-corner art without a dark gradient or duplicate hover outline; hide game names and click instructions; show a smaller bottom-right Ready/Broken/Absent badge whose text reveals on hover; and use one large centered Edit/Repair/Add action icon. Broken cards must list their specific problems.

## comment 5464858277 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5464858277

Created: 2026-08-29T21:00:58Z; updated: 2026-08-29T21:00:58Z

Exact metadata: [source record](sources/comment-5464858277-d140150fead895ae454ed96be086ea208f9e38575c18345c0cbae49c460c5bbb.json).

The home cards now use square, unshaded box art with one border. Hover shows a large Edit, Repair, or Add icon, a small Ready/Broken/Absent badge, and useful details only. Broken always lists its cause; games without fonts show no font control. I rendered and inspected all three states.

## comment 5471754379 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5471754379

Created: 2026-08-30T22:51:15Z; updated: 2026-08-30T22:51:15Z

Exact metadata: [source record](sources/comment-5471754379-dd811135cefe9ef527d6400e40f68fbf186788a37b006b9d3cf21a89503928dd.json).

Home follow-up: add permanent GitHub and Twitter buttons at bottom-left. GitHub opens the Lexeditor repository; Twitter opens @LexerLux and swaps its bird for the X mark only while hovered. Also make the Home top-menu height a user percentage setting.

## comment 5471817615 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5471817615

Created: 2026-08-30T23:05:18Z; updated: 2026-08-30T23:05:18Z

Exact metadata: [source record](sources/comment-5471817615-aad52388d261b77a0b796aaff81112a4b0aa9796d5bd9fb395ae716e98bf75a0.json).

Home now has permanent bottom-left GitHub and @LexerLux Twitter buttons. Twitter changes from the bird to X on hover. Main menu height is a 7–20% user setting with a 9% default; the rendered 900 px test measured 81 px and opened only the two fixed host allowlist targets.

## comment 5472059252 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5472059252

Created: 2026-08-30T23:56:46Z; updated: 2026-08-30T23:56:46Z

Exact metadata: [source record](sources/comment-5472059252-0526b9539e31b05f13086d358e379fc65b5ce779fae5e7b1c6dd29e63c63883b.json).

Startup currently rechecks only game roots that Lexeditor already saved. That is why newly installed supported games can stay Absent, while saved games validate quickly and RDR1 remains Scanning during its longer preparation step. I am changing startup to scan every managed plugin through Steam's library and app manifests first, then validate that plugin's required files.

## comment 5472089261 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5472089261

Created: 2026-08-31T00:03:09Z; updated: 2026-08-31T00:03:09Z

Exact metadata: [source record](sources/comment-5472089261-0ce3ce36a2e78e700763d37600ff3449e4f0a7c36d77e28d4928470bc9942e51.json).

Automatic game discovery is repaired. Every managed plugin now scans on startup, even with no saved Lexeditor path. Discovery checks Steam manifests first, validates only the plugin's declared required files, persists valid roots, and does not probe guessed folders across every drive. Expensive archive extraction is no longer part of startup discovery; it runs when that plugin opens. An empty-config test found a new install, left a missing game Absent, proved startup did not prepare data, and passed the rendered Home and full-host regressions.

## comment 5472127432 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5472127432

Created: 2026-08-31T00:10:04Z; updated: 2026-08-31T00:10:04Z

Exact metadata: [source record](sources/comment-5472127432-24570c9a86a60158140900038cdcb29141312957a26bfb3ff06df05689102ed1.json).

Home follow-up: enlarge the Absent status symbol and desaturate only Absent cover art. The desaturation amount will be a bounded Lexer-only packaged default, so it controls the presentation for everyone without becoming a personal user setting.

## comment 5472166216 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5472166216

Created: 2026-08-31T00:16:07Z; updated: 2026-08-31T00:16:07Z

Exact metadata: [source record](sources/comment-5472166216-8fdfb36f86a1695658752494f47eda0fcebc534d0376bb421ccb43aa64abb7a3.json).

The Absent badge now uses a larger heavy X, and only Absent cover art is desaturated. The rendered default is 75%. Ready and Broken art remains unchanged. The Home render and full hidden desktop-host checks passed.

## comment 5472901580 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5472901580

Created: 2026-08-31T02:20:31Z; updated: 2026-08-31T02:20:31Z

Exact metadata: [source record](sources/comment-5472901580-13b888ae3578915ef5d822ace44503ea2d2d8e51d316182378d703eecf747f96.json).

Home no longer shows ‘Choose a game.’ A game’s full name now slides onto the top of its card only on hover or keyboard focus. Blank Game has packaged portrait art, and the new FFVII now uses Steam’s locally cached 300×450 library capsule before trying the missing public artwork URL.

## comment 5473157756 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5473157756

Created: 2026-08-31T03:02:06Z; updated: 2026-08-31T03:02:06Z

Exact metadata: [source record](sources/comment-5473157756-b918ae6515a163d2fc0d0c1f02859c8956fe344c8dface76d68f4c5d4d33305a.json).

Blank: The Game now uses original portrait box art with a visible E-for-Everyone rating block. On Home, a hovered game name now slides completely above the cover instead of ending inside it. The hidden 1440x900 render confirmed the title geometry and packaged cover.

## comment 5473231803 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5473231803

Created: 2026-08-31T03:13:44Z; updated: 2026-08-31T03:13:44Z

Exact metadata: [source record](sources/comment-5473231803-dc258be9604c03434153a85c1be901c4b178fb8b0553cff7c9c60b0a970795e9.json).

Blank: The Game now carries the official HD ‘Featuring Dante from the Devil May Cry series’ sticker at bottom-right, opposite the ESRB block. The edited 1024x1536 cover preserves the title, doorway, and rating.

## comment 5473359891 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5473359891

Created: 2026-08-31T03:33:37Z; updated: 2026-08-31T03:33:37Z

Exact metadata: [source record](sources/comment-5473359891-043279a6cde33d5e75a91c796ff617f227d1dcd9d3be91c4a853331b5a6ddb56.json).

Hovered game names now use the Home grid's full 52-pixel row gap. The title is plain text with a transparent background and no box shadow; its band ends exactly at the card's top edge. The rendered Home check passed.

## comment 5473366280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5473366280

Created: 2026-08-31T03:34:44Z; updated: 2026-08-31T03:34:44Z

Exact metadata: [source record](sources/comment-5473366280-da29c6388b37a16ef4e4f4a743cf2ddd57066e65a4f84dd6e181c33c5063e27a.json).

The folder and version controls still reserved the old in-cover title height. Both now use the normal 12 px internal top inset, placing them back in the top-left and top-right corners. The Home render measured both at 15 px from the card's outer edge, including its 3 px border.

## comment 5486972116 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/22#issuecomment-5486972116

Created: 2026-09-01T01:04:05Z; updated: 2026-09-01T01:04:05Z

Exact metadata: [source record](sources/comment-5486972116-bcb613ec17ef0e2feecdd52e185692396199e6cb6bcaeda351c1c175b145ae49.json).

Restored the Home minimize, maximize, and close controls to opaque bordered squircle buttons. The rendered 1440 x 900 check now asserts the 11 px radius, solid border, visible background, and full opacity so the transparent regression cannot pass again.
