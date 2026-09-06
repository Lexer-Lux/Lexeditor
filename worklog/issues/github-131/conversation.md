# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356291314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131

Created: 2026-08-06T02:10:38Z; updated: 2026-09-05T06:56:31Z

Exact metadata: [source record](sources/issue-5356291314-b9e02e2153e5c1c40160dca55f5541ea4f250a9f49461083319464b9f66b0d80.json).

ALCOHOL CONSUMABLE EFFECTS — I want to edit how strong each drink is.
     The real per-drink alcohol values (0.10-0.50 on the game's 0-1 scale;
     Sober 0-0.49, Drunk 0.50-0.74, Wasted 0.75-0.99, Blackout 1) are not in the
     catalog and are not the drink-class tag — Moonshine 0.30 and Gin 0.17 share
     the same tag. Find where that data actually lives, bring it into the
     project, and expose the numeric value per drink in LEXEDITOR as a real
     field (the current "Drink class" selector is only the coarse tag).
     If I don't get this working -- moonshine instant KO specifically --
     then the "pass out to Guarma" exploit might not work due to decreased carry
     limits, which could be extra bad because I want that one challenge
     implemented that relies on it.

## issue 5356291314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131

Created: 2026-08-06T02:10:38Z; updated: 2026-09-06T12:46:58Z

Exact metadata: [source record](sources/issue-5356291314-3e73ea7b7322fdfb321dc6ce695d5487afe234a79acb417f0a404fed1b4aed5a.json).

Expose each drink’s real alcohol strength separately from its coarse drink-class tag. Preserve the requested strong-Moonshine behavior.

**Status: Reported broken.** The latest report says the numeric strengths all became 1. Restore and validate the real per-drink values before requesting another test.

## issue 5356291314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131

Created: 2026-08-06T02:10:38Z; updated: 2026-09-06T13:54:36Z

Exact metadata: [source record](sources/issue-5356291314-a9f9a07ce153ca6ef520fca810d71f9f70c5c786e1b697a5d5885d8823e38714.json).

Expose each drink’s real alcohol strength separately from its coarse drink-class tag. Preserve the requested strong-Moonshine behavior.

**Status: Reported broken.** The latest report says the numeric strengths all became 1. Restore and validate the real per-drink values before requesting another test.

## issue 5356291314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131

Created: 2026-08-06T02:10:38Z; updated: 2026-09-06T15:00:37Z

Exact metadata: [source record](sources/issue-5356291314-f97e897e17af3f52d05e48bad4e7727b646d7a2a4300b8a0f86d62774d07ca4c.json).

Expose each drink’s real alcohol strength separately from its coarse drink-class tag. Preserve the requested strong-Moonshine behavior.

**Status: Reported broken.** The latest report says the numeric strengths all became 1. Restore and validate the real per-drink values before requesting another test.

## issue 5356291314 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131

Created: 2026-08-06T02:10:38Z; updated: 2026-09-06T16:29:15Z

Exact metadata: [source record](sources/issue-5356291314-11dbde815bc147eadf46584d2f7220f1ed66ce06773dad3a32567ace352d9946.json).

Expose each drink’s real alcohol strength separately from its coarse drink-class tag. Preserve the requested strong-Moonshine behavior.

**Status: Reported broken.** The latest report says the numeric strengths all became 1. Restore and validate the real per-drink values before requesting another test.

## comment 5550117968 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131#issuecomment-5550117968

Created: 2026-08-06T05:39:44Z; updated: 2026-08-06T05:39:44Z

Exact metadata: [source record](sources/comment-5550117968-12764dd9466b5fae253e2867b75a69a5739e54293165160465574bdde33fb4b4.json).

The editor now imports all 14 vanilla per-drink values and stores sparse 0-1 overrides; runtime integration replaces Rockstar's per-swig result with the configured total and uses the real alcohol global/blackout path. Static checks and the ASI build pass. Because RDR2 is running, the hash-verified install is queued for game exit; this remains actionable until it lands, then it will move to test me.

## comment 5550117975 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131#issuecomment-5550117975

Created: 2026-08-06T09:12:19Z; updated: 2026-08-06T09:12:19Z

Exact metadata: [source record](sources/comment-5550117975-441d19fbefd6c0a62379ebbdc194053e3477b93c111fe52142c9dc1588eaad81.json).

<img width="620" height="79" alt="Image" src="https://github.com/user-attachments/assets/4d427c16-87ed-41ce-b0c6-0fa6e00310e5" />
wait before this i saw actual numerical values in the editor for booze. now every single one has been replaced with a 1. i don't understand what you did. was this already done and you just broke it?

## comment 5560077142 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131#issuecomment-5560077142

Created: 2026-09-06T15:00:37Z; updated: 2026-09-06T15:00:37Z

Exact metadata: [source record](sources/comment-5560077142-b56e9871a18c0a06333ceaa6f2a0d9e463ea7a5d242920f8eac8c3deb73d2b3a.json).

Partial repair candidate in #364. Confirmed unsafe save behavior is fixed: the browser sends only edited drinks; the backend merges with current persisted overrides rather than overwriting unrelated newer values. Invalid/non-finite/out-of-range inputs are rejected, unknown saved entries cannot be silently dropped, missing baselines are explicit, and float round-trip precision is retained.

The current source data has distinct per-drink strengths; the deliberate Moonshine=1 value is preserved. I did not reproduce the reported universal-1 display, so this is not a proven diagnosis of that original symptom. Regression tests cover sparse saves, unrelated concurrent changes, precision, invalid input, and unavailable baselines.

The source PR is draft, with no full browser/visual acceptance performed. Keep this issue open/actionable pending comparison of the rendered values against the selected CSV. Existing requests and the new implementation handoff are retained.

## comment 5560582972 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/131#issuecomment-5560582972

Created: 2026-09-06T16:29:15Z; updated: 2026-09-06T16:29:15Z

Exact metadata: [source record](sources/comment-5560582972-be96b4c06d8dc17dc22e03dc5b18a1d97810cacee94f9fcd0a4f9006e46346b7.json).

Fixed another reproduced defect in #364: editing only Drunkenness and pressing header Save reported success without saving. The global Save dispatcher now sends that edit; rejected writes retain it and cannot report success.

The actual rendered editor passed three offline browser cases (save, failure, unavailable data), plus two new production save-handler tests. Distinct baseline values and the deliberate Moonshine=1 override remain separate. This does not establish the original all-ones symptom's cause in your real project; the issue stays actionable.
