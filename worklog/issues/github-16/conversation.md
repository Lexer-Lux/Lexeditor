# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5234852285 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16

Created: 2026-08-24T12:45:06Z; updated: 2026-09-04T12:24:35Z

Exact metadata: [source record](sources/issue-5234852285-6230f9a90475d0e7b183fa86b18063b9f4ed950f110947ded2177c9511370bc9.json).

## Goal

When RDR2 is added or opened with an empty Lexeditor cache, prepare every vanilla game-data file that the active RDR2 editor needs. Do not require OpenIV or a manual export.

## Required behavior

- Use a bundled, licensed, read-only headless extractor.
- Extract the complete baseline for the active Items, Effects, Loot, Challenges, Weapons, Crime, Bounty Hunters, Ped Perception, Combat, and Ped Health pages.
- Convert Rockstar binary metadata to validated XML where the editor needs XML.
- Keep model-preview extraction lazy. Do not dump the whole model library at startup.
- Store results only in Lexeditor's private cache. Never write to a game archive.
- Use an explicit manifest, source stamps, atomic replacement, and clear per-file errors.
- A failed or unsupported file keeps RDR2 in Warning state. It must not be reported as ready.

## Acceptance

Start with an empty RDR2 cache and the current game archives. Add RDR2 once. Preparation must finish without OpenIV, every required output must parse as XML, and every active RDR2 data page must load its vanilla reference without a missing-baseline error.

## issue 5234852285 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16

Created: 2026-08-24T12:45:06Z; updated: 2026-09-06T12:45:06Z

Exact metadata: [source record](sources/issue-5234852285-34beb395ce83252ffbbf9a7376070021ee15a588485dda7eb5ee9029edeb464c.json).

First-start preparation now uses the bundled converter. Clean-cache checks passed for the required data; your normal-install check remains.

- [ ] Restart Lexeditor and rescan RDR2. Confirm preparation finishes at Ready without requesting OpenIV or a developer checkout.
- [ ] Open Items, Quick Select, Loot, Challenges, Crime, Dispatch, Weapons and Mobs. Confirm Vanilla data loads; report the first failing page and its error text.

## issue 5234852285 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16

Created: 2026-08-24T12:45:06Z; updated: 2026-09-06T12:45:06Z

Exact metadata: [source record](sources/issue-5234852285-97798cb8c6d9921a7de1e3fd491a3756e097a22b6a38143272bcf096cd4f846a.json).

First-start preparation now uses the bundled converter. Clean-cache checks passed for the required data; your normal-install check remains.

- [ ] Restart Lexeditor and rescan RDR2. Confirm preparation finishes at Ready without requesting OpenIV or a developer checkout.
- [ ] Open Items, Quick Select, Loot, Challenges, Crime, Dispatch, Weapons and Mobs. Confirm Vanilla data loads; report the first failing page and its error text.

## comment 5473713407 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16#issuecomment-5473713407

Created: 2026-08-31T04:26:57Z; updated: 2026-08-31T04:26:57Z

Exact metadata: [source record](sources/comment-5473713407-42e9ab045634cc0a1c75a511af0da6d947beba209851baff1da67a2855711b84.json).

I mapped the complete installed RDR2 source set. Loot, matrix, crime, dispatch, goals, and challenges are directly extractable XML, and Quick Select is convertible RBF0. The two files that prevent full first-start readiness are the effective catalog and weapons data: both are PSIN resources, and the bundled RBF converter rejects PSIN. I recorded the exact archive chains and sizes. I have not mislabeled raw PSIN as ready XML or changed any game archive; issue #16 remains actionable until a proven PSIN decoder is integrated.

## comment 5477536028 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16#issuecomment-5477536028

Created: 2026-08-31T11:16:51Z; updated: 2026-08-31T11:24:53Z

Exact metadata: [source record](sources/comment-5477536028-45dc580b91e6879bfb0f14f6dd4a3d778567738f467de5281f69bea84e86b6c0.json).

Implemented complete first-start preparation for the active RDR2 editor pages. Lexeditor now prepares 28 required outputs in its private cache, including the catalog, quick-select data, loot, challenges, crime, dispatch, all active weapon layers, and all four weapon-component layers.

The PSIN path is fail-closed: Lexeditor extracts and hashes the installed source, then uses the matching validated XML baseline only for the proved game build. An unknown build stays in Warning with the affected file instead of receiving guessed or partial XML.

Verified against the current Steam installation with an empty cache: all 28 outputs validated, the second run did no work, an unknown PSIN hash was rejected, and every active Vanilla data endpoint loaded through the hosted RDR2 service. RDR2 was not launched or modified.

Please restart Lexeditor, add/open RDR2, and confirm that its card reaches Ready and the data pages open normally.

## comment 5477649503 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16#issuecomment-5477649503

Created: 2026-08-31T11:28:36Z; updated: 2026-08-31T11:28:36Z

Exact metadata: [source record](sources/comment-5477649503-29c611dcea45ef4ff5941f9f1678bba9d4e2e07a0a8f480618ce5c4adeccfd5b.json).

The independent clean-cache audit found three completion defects: Bounty Hunters is written under a path the endpoint does not read, the Vanilla Weapons endpoint loads only the base file instead of all seven active layers, and the PSIN snapshot source still depends on the separate C:\RDR2Mod developer checkout. The verifier also failed to catch these states. I moved this back to actionable and am correcting the paths, bundled resources, layer loading, and acceptance checks.

## comment 5478191871 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16#issuecomment-5478191871

Created: 2026-08-31T12:15:19Z; updated: 2026-08-31T12:15:19Z

Exact metadata: [source record](sources/comment-5478191871-694775cd3c94159294079421dcb4489365b6adb3dab39ddd1cebf85b10f806f4.json).

Corrected the false-readiness and verifier defects. RDR2 now stays in Warning/preparing and cannot open until data preparation succeeds; a preparation error remains Warning with the exact failure. Cache dependencies now include content fingerprints, and the four previously weak XML checks require their real root schemas.

The clean-cache verifier now mutation-tests those states and checks useful fields from every active endpoint. It passes against the installed archives without launching RDR2. Issue #16 remains actionable because the catalog and weapon PSIN files still need a bundled converter; the current developer-checkout baselines are not a valid user installation path.

## comment 5479007903 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/16#issuecomment-5479007903

Created: 2026-08-31T13:23:41Z; updated: 2026-08-31T13:23:41Z

Exact metadata: [source record](sources/comment-5479007903-da6c0039823288a5029d6e8ce48a6ae1ed59f0e6e3fbb53e9568ead454eded79.json).

The remaining first-start blocker is fixed. Lexeditor now converts the installed RDR2 catalog and all seven weapon PSIN files with the bundled licensed reader; it no longer reads validated XML from `C:\RDR2Mod` or any other developer checkout. Unknown schema members are preserved by hash, and an unsupported game-file hash still fails closed.

I verified this from an empty private cache against the installed game. All 28 outputs passed validation, every active Vanilla endpoint returned useful data, a copied minimum Lexeditor installation prepared successfully, and a forced converter failure left the card in Warning with opening disabled and no partial file.

Please restart Lexeditor, remove/re-add RDR2 or trigger its scan, and confirm that the card reaches Ready and that Catalog, Quick Select, Loot, Challenges, Crime, Dispatch, Weapons, and Mobs open with Vanilla data. RDR2 was not launched or modified during verification.
