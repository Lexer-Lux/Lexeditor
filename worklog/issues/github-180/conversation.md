# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-05T06:59:04Z

Exact metadata: [source record](sources/issue-5356302029-a68f5f47b66523fe589bb758282e5e31f87489461569154e7df72599d6040ef9.json).

## Requirement

Attach the same casing glint effect to uncollected cigarette-card pickups in the world. The glint is required, not an optional default-off experiment.

- Use the existing casing effect and its current tuning.
- Attach it to Rockstar's real streamed card object. Do not create a replacement card or visible proxy.
- Search only nearby streamed cards at a bounded cadence.
- Do not glint collected cards.
- Clean up the effect when the card is collected, unloads, or ceases to exist.
- Preserve the vanilla pickup prompt and Eagle Eye behavior.

Acceptance: nearby uncollected cigarette cards are easy to locate because they carry the same subtle glint as casings, with no duplicate objects, stale particles, or effect on collected cards.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-06T13:25:01Z

Exact metadata: [source record](sources/issue-5356302029-bc4fadabd2fbd377b575463c549a5e009ed87a726cb059c26346475676718295.json).

**Actionable — removal remains.** You asked to remove this feature because vanilla cigarette cards already flash. Later implementation notes did not supersede that decision.

Remove the custom card-glint code and setting while preserving vanilla flashes, card pickups and the separate casing glints. No new design answer or repeat test is needed from you.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-06T13:56:06Z

Exact metadata: [source record](sources/issue-5356302029-8e503e6ea47db8f63581ce4c517dbc1e8e8787f7f63957e877cb3b14046f3602.json).

**Actionable — removal remains.** You asked to remove this feature because vanilla cigarette cards already flash. Later implementation notes did not supersede that decision.

Remove the custom card-glint code and setting while preserving vanilla flashes, card pickups and the separate casing glints. No new design answer or repeat test is needed from you.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-06T17:14:39Z

Exact metadata: [source record](sources/issue-5356302029-c4f3db52ef49adebefcf96ccc2e514f6e443af614a16baa6e80a375f2fc2d0bd.json).

**Actionable — removal remains.** You asked to remove this feature because vanilla cigarette cards already flash. Later implementation notes did not supersede that decision.

Remove the custom card-glint code and setting while preserving vanilla flashes, card pickups and the separate casing glints. No new design answer or repeat test is needed from you.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-06T17:34:19Z

Exact metadata: [source record](sources/issue-5356302029-211dbd13d2e5ae95ca8323bf2ea7568b75e4583daf943240218ed0c011977df8.json).

**Actionable — removal remains.** You asked to remove this feature because vanilla cigarette cards already flash. Later implementation notes did not supersede that decision.

Remove the custom card-glint code and setting while preserving vanilla flashes, card pickups and the separate casing glints. No new design answer or repeat test is needed from you.

## issue 5356302029 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180

Created: 2026-08-06T03:45:31Z; updated: 2026-09-06T17:34:19Z

Exact metadata: [source record](sources/issue-5356302029-ee9a69d1b8ab923bf35ee1067c614b4338fffbc667807907fbbec5ca651b194f.json).

**Completed and merged.** Runtime PR Lexer-Lux/Lexers-Mod-For-RDR2#211 removed the redundant custom cigarette-card glint implementation and setting while retaining unrelated spent-casing glints. Permanent regression checks passed on the merged runtime candidate.

Vanilla cigarette-card flashing remains the intended behavior; no repeat design or acceptance test was requested for this removal.

## comment 5550130360 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5550130360

Created: 2026-08-06T05:44:39Z; updated: 2026-08-06T05:44:39Z

Exact metadata: [source record](sources/comment-5550130360-657ebe9f0c25c31ebd0e6b0e8d7dfa92e96da9b67bba9515bead995884183dfb.json).

Implemented as a default-off INI option that attaches the casing-style glint to Rockstar's real uncollected cigarette-card objects, with nearby/throttled discovery and cleanup on collection or streaming. Combined ASI build passes and hash-verified install is queued for RDR2 exit, so this remains actionable until it lands.

## comment 5550130378 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5550130378

Created: 2026-08-06T07:52:43Z; updated: 2026-08-06T07:52:43Z

Exact metadata: [source record](sources/comment-5550130378-d2e0a4987e0c2a08dbc0e6b09ae76359573afe7eede5b2cb1a855cf105d590ee.json).

dsoent' seem to work but i forgot that they already flash in vanilla. so just get rid of this feature and its code it's not necessary

## comment 5550130388 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5550130388

Created: 2026-08-06T08:59:02Z; updated: 2026-08-06T08:59:02Z

Exact metadata: [source record](sources/comment-5550130388-2c696554887ebc49eba77320babbc3f39523f7fa610748d854c1e9328f321d46.json).

Optional cigarette-card glints, separate from casing glints, are integrated and installed in `C92A04F…CCA3`. Moved to `test me` for world-card/streaming cleanup checks.

## comment 5550130401 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5550130401

Created: 2026-08-06T09:18:57Z; updated: 2026-08-06T09:18:57Z

Exact metadata: [source record](sources/comment-5550130401-412a28892e771919d6c559c76c9148176bd47ef651362a58d65d543d6c442bda.json).

Correction: you explicitly asked for this unnecessary feature and its code to be removed because vanilla cards already flash. It was wrongly sent back to test me. This is actionable until the feature is actually removed.

## comment 5550130414 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5550130414

Created: 2026-08-20T19:43:00Z; updated: 2026-08-20T19:43:00Z

Exact metadata: [source record](sources/comment-5550130414-c55a0477e1a168c4e09a877b793efa11c74c3b72d948f734d34bbfec1a3122db.json).

Source repair is complete but unbuilt. The casing glint is now attached to the real streamed cigarette-card object for all 144 card models. Discovery is limited to nearby authored placements, and the effect is removed when the card is collected, hidden, or streamed out. The code does not create, move, replace, or collect cards. After the next install, confirm that an uncollected card glints and remains normally inspectable and collectible.

## comment 5560839232 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/180#issuecomment-5560839232

Created: 2026-09-06T17:14:39Z; updated: 2026-09-06T17:14:39Z

Exact metadata: [source record](sources/comment-5560839232-88610c85c0fb8d471ed364d22b47834aa6303cd09643ab34159eae70bc8f2f71.json).

Verified the custom cigarette-card glint implementation is absent and kept that retirement under permanent CI. The regression also confirms unrelated spent-casing glints remain. No replacement card-glint code was added and I am not asking you to repeat the previously rejected visual test. Current Windows candidates build successfully in runtime PR #211; merge/delivery remains separate from source verification.
