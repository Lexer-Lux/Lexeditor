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
