# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356302883 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184

Created: 2026-08-06T03:56:34Z; updated: 2026-09-05T06:59:16Z

Exact metadata: [source record](sources/issue-5356302883-20b32fd19b0deb9497a8f7a14843766423be03ecebdabec81b945bdb563b52aa.json).

## Player-facing behavior

Add a canteen inventory item that stores multiple drinks rather than being consumed after one use.

Using the canteen consumes one stored drink and restores Stamina Core. The restoration amount is configurable in the developer section of `GameplayTweaks.ini`.

## Requirements

- Add a usable canteen item with a visible remaining-use count or another clear way to tell how much water remains.
- Give it a defined maximum capacity greater than one use.
- Each use consumes exactly one charge.
- Each use restores Stamina Core by the configured amount.
- Add a developer INI setting for the Stamina Core restoration per drink.
- Decide and implement sensible behavior when the canteen is empty.
- Persist the canteen's remaining water across save/load if the available inventory/item mechanism supports it; document any proven engine limitation if it does not.
- Do not make the canteen disposable after a single drink.

## Acceptance test

1. Obtain the canteen and confirm it has multiple uses.
2. Drink repeatedly and verify one charge is consumed each time.
3. Verify each drink restores the configured amount of Stamina Core.
4. Change the developer INI value, reload as required, and confirm the new amount is used.
5. Empty the canteen and confirm it cannot provide further restoration until refilled.
6. Save/reload with a partially filled canteen and verify the remaining amount persists, subject to any documented engine limitation.

## issue 5356302883 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184

Created: 2026-08-06T03:56:34Z; updated: 2026-09-06T12:55:13Z

Exact metadata: [source record](sources/issue-5356302883-b95135acf65301d62aec5d9b33734c0ae245270023d9bdf124426777975b31ef.json).

The reusable canteen stores five drinks, consumes one charge per use, restores configured Stamina Core and retains its water across reloads. It is crafted from one Empty Bottle at a campfire.

**Status: An earlier candidate was installed, but the required custom-crafting flow still has undelivered repairs in #122.** Verify that combined build and its acquisition route before requesting final canteen/refill tests.

## issue 5356302883 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184

Created: 2026-08-06T03:56:34Z; updated: 2026-09-06T13:57:09Z

Exact metadata: [source record](sources/issue-5356302883-f2fa6e4341344e23279f4f77b9860f0760fab259c5636f4c4d5ca2c7c9f14ab2.json).

The reusable canteen stores five drinks, consumes one charge per use, restores configured Stamina Core and retains its water across reloads. It is crafted from one Empty Bottle at a campfire.

**Status: An earlier candidate was installed, but the required custom-crafting flow still has undelivered repairs in #122.** Verify that combined build and its acquisition route before requesting final canteen/refill tests.

## comment 5550131378 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131378

Created: 2026-08-06T07:05:50Z; updated: 2026-08-06T07:05:50Z

Exact metadata: [source record](sources/comment-5550131378-e6ac01ea158689aaa1f0bb628fbadd80994932d100566f18a62e48d7fff1d7b2.json).

Implementation update: integrated a five-charge reusable canteen using the existing LEX_WATER_BOTTLE interaction shell. One confirmed native consumption spends one persisted charge, restores the exact hot-reloaded [CanteenDeveloper] StaminaCorePerDrink amount, restores the reusable shell, and reports N/5 or empty. Crafting it from one Empty Bottle initializes full; multiplicity is now one item rather than five disposables. I removed only its old fixed +25 effect after decompiled ordering proved it would visibly restore even an empty canteen before correction; the authored animation/consumption remains. Combined release build and live LEXEDITOR recipe load pass. Keeping actionable until the corrected deferred install lands.

## comment 5550131394 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131394

Created: 2026-08-06T07:49:32Z; updated: 2026-08-06T07:49:32Z

Exact metadata: [source record](sources/comment-5550131394-45f2d697272a1b02fccdc89e2393bf20f3154978dfc9351461ffbd44ec2d4192.json).

??? where do i find the canteen

## comment 5550131405 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131405

Created: 2026-08-06T11:26:54Z; updated: 2026-08-06T11:26:54Z

Exact metadata: [source record](sources/comment-5550131405-2218f3c4ab8a42d06392fc2f0a779d41790f9dfe8b2965c8aa3dbda508eef442.json).

where do i find the canteen.

## comment 5550131416 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131416

Created: 2026-08-06T12:07:01Z; updated: 2026-08-06T12:07:01Z

Exact metadata: [source record](sources/comment-5550131416-07de30767af4e8941ad34b6df4900ecd9efef4dd867e5b784d6cb70bab12e749.json).

WHERE. DO. I. FIND. THE. CANTEEN.

## comment 5550131424 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131424

Created: 2026-08-06T12:08:00Z; updated: 2026-08-06T12:08:00Z

Exact metadata: [source record](sources/comment-5550131424-12865c108dd85e96aec5e793054c8c97936c68a9456b07c41021d8e129cf69ad.json).

The canteen is obtained by crafting it at any campfire from 1 Empty Bottle in the custom crafting menu; it is not a world pickup. The corrected custom-crafting/canteen candidate is installed on disk for the next full restart in ASI D4189A...1AC8. Moved to 	est me; no runtime result claimed.

## comment 5550131438 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/184#issuecomment-5550131438

Created: 2026-08-06T13:03:17Z; updated: 2026-08-06T13:03:17Z

Exact metadata: [source record](sources/comment-5550131438-a2a6f321b3f44546e7ccca9b53afc382a0d2915a1ca6edf1c0c93ca3ad9d383b.json).

Current live runtime proof: the installed ASI loaded the reusable-canteen module and posted the acquisition hint in this game session (`acquisition-hint campfire empty-bottle=1`). Obtain it by opening Crafting at any campfire, selecting `Reusable Canteen`, and crafting it from 1 Empty Bottle. Then test 5/5 charges, one-charge-per-drink, configured Stamina Core restoration, empty behavior, pump refill, and save/reload persistence. This is now a real installed acceptance test, so it belongs in `test me`.
