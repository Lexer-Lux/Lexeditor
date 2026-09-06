# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5288099278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/55

Created: 2026-08-29T18:10:28Z; updated: 2026-09-04T12:24:57Z

Exact metadata: [source record](sources/issue-5288099278-e3c5f417a3738ed132c1d928d17b1d62f45487d3ef5da934c8a71ae25743e25f.json).

Warband and RDR2 become ready immediately from valid saved locations and caches, but RDR1 and FF8 visibly scan/prepare again on every Lexeditor launch.\n\nConfirmed causes:\n- RDR1 cache validation includes the packed and unpacked .wgd controls in an XML-parse loop. Both are non-XML data, so validation always returns false even when the manifest, archive fingerprints, tool fingerprint, counts, and required files match.\n- FF8 manifest file keys already begin with en/. baseline_ready() checks them below baseline/en/, producing baseline/en/en/... paths. All 212 prepared files are therefore reported missing and the baseline is extracted again.\n\nFix both validators, add warm-cache mutation tests that fail on the current behavior, and confirm a second startup performs validation only without rewriting either manifest or launching extractors. RDR2's stamp/output cache and Warband's path-only validation are the controls.

## issue 5288099278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/55

Created: 2026-08-29T18:10:28Z; updated: 2026-09-06T13:06:52Z

Exact metadata: [source record](sources/issue-5288099278-16a5603c18e2c7dd3e269176b63b2996e1116b2fe0834bfbd361a56aefdd1473.json).

**Status: Both cache checks are repaired; needs your startup check.** Valid prepared data should be reused rather than extracted every time.

- [ ] With RDR1 and FF8 already prepared, fully close and reopen Lexeditor, then open each plugin. Do not delete their caches.
- [ ] Repeat once without changing the games. Confirm neither runs full extraction again; a brief readiness check is normal. Report the game and message that repeats.

## comment 5473643581 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/55#issuecomment-5473643581

Created: 2026-08-31T04:17:39Z; updated: 2026-08-31T04:17:39Z

Exact metadata: [source record](sources/comment-5473643581-e59eafaa9824b0c9dedde27090085bc466eec5b35e0e1f14a46eba929c337e45.json).

Both warm-cache validators are repaired and now have mutation coverage. The test called the normal FF8 and RDR1 preparation paths twice with extractor traps installed: no extractor ran and neither manifest timestamp changed. Removing an FF8 prepared file and corrupting an RDR1 packed WGD correctly invalidated each cache. Your current private FF8 and RDR1 caches both validate as ready against the installed archives. Please restart Lexeditor once and confirm neither game shows extraction progress.
