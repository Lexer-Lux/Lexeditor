# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356538763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/347

Created: 2026-09-05T07:52:17Z; updated: 2026-09-06T12:24:34Z

Exact metadata: [source record](sources/issue-5356538763-fb9975b6200a11df06876272ea03a622cbf9da0575444cf21552b1ca98af46a3.json).

The RDR2 editor takes too long to open. Reduce the delay without removing the loading screen or opening incomplete data.

**Status: Deferred investigation.** No startup-speed fix is ready to test.

## issue 5356538763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/347

Created: 2026-09-05T07:52:17Z; updated: 2026-09-06T13:32:10Z

Exact metadata: [source record](sources/issue-5356538763-61e209d883c7efdf84a9745f8570c837c6efea978a98be2c087f037f59b84176.json).

**Actionable — investigation deferred.** Opening the plugin is too slow. Reduce the delay without removing the loading screen or displaying incomplete data.

No startup-speed repair is ready to test; no action from you is blocking it.

## issue 5356538763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/347

Created: 2026-09-05T07:52:17Z; updated: 2026-09-06T13:32:10Z

Exact metadata: [source record](sources/issue-5356538763-e6ff67a571da0fbd84099e75d53dbc9f29afa0170700e0da7040181511dd8237.json).

**Actionable — investigation deferred.** Opening the plugin is too slow. Reduce the delay without removing the loading screen or displaying incomplete data.

No startup-speed repair is ready to test; no action from you is blocking it.

## issue 5356538763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/347

Created: 2026-09-05T07:52:17Z; updated: 2026-09-06T17:33:24Z

Exact metadata: [source record](sources/issue-5356538763-1f500b2d7b35da3e5fd74e1e47d2b379f4fb7f2fbfca1b1023b8d43a8d0a5918.json).

**Implemented and merged — needs real startup acceptance.** PR #364 is merged into `master` as `70121f7a39d2dc218025c9b94ef12021e50c8317`.

The RDR2 editor now reuses catalog caches for localization/crafting, honors mapped paths, keeps per-dataset provenance caches, invalidates them when localization changes, loads independent requests concurrently, keeps the loading screen visible through required data/render, and ignores superseded dataset responses.

Automated integration evidence measured the localization/crafting/catalog path at median 7.460s -> 4.145s (44.4% lower) with identical response hashes. That is not a full Windows/WebView2 launch benchmark.

- [ ] Update to current `master`, fully restart Lexeditor, and time RDR2 from selection until the editor is usable.
- [ ] Confirm no incomplete/blank data flashes before loading finishes.
- [ ] Report the observed startup time and first page that still feels delayed, if any.

## issue 5356538763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/347

Created: 2026-09-05T07:52:17Z; updated: 2026-09-06T17:33:24Z

Exact metadata: [source record](sources/issue-5356538763-d826f4559945d84cff542364dbfdfa6c834011df98c8d7506db186e33a222609.json).

**Actionable — investigation deferred.** Opening the plugin is too slow. Reduce the delay without removing the loading screen or displaying incomplete data.

No startup-speed repair is ready to test; no action from you is blocking it.
