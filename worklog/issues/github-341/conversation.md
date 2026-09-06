# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356489261 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/341

Created: 2026-08-24T16:26:53Z; updated: 2026-09-05T07:40:55Z

Exact metadata: [source record](sources/issue-5356489261-05d23cc5856db40977911139912be5602d8797c632dd6953a4fd7efd852f8ed8.json).

Add a Shops tab to the RDR Lexeditor plugin. Derive stores, stock, prices, quantities, and supported conditions from the real RDR ShopInventory Gringo data and the shopkeeper script. Preserve unknown fields. Save only isolated project overrides and never write an installed RPF archive. Acceptance: the tab lists each resolved store and its real stock, edits supported values, saves and reads them back without losing unsupported data, and the edited values are confirmed in the matching shop in-game.

## issue 5356489261 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/341

Created: 2026-08-24T16:26:53Z; updated: 2026-09-06T12:39:00Z

Exact metadata: [source record](sources/issue-5356489261-2a34b64cc0d9051c195bd8db86432475d3dac1af46de7f7b1ce472de2605504a.json).

**Status: Shops editing is implemented; in-game delivery remains unverified.** The editor supports stock, purchase quantities and price modifiers for 20 shops.

Prepare one named shop/item, a known test value and the exact deployment/revert steps before asking you to visit it. An editor save/readback alone does not prove the shop changed in game.

## comment 5550350838 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/341#issuecomment-5550350838

Created: 2026-08-24T17:02:43Z; updated: 2026-08-24T17:02:43Z

Exact metadata: [source record](sources/comment-5550350838-b08160f2f48d6aa4206aad983f774dd26894633bc662f5c3defbfc9f849be3a0.json).

The Shops tab now reads the real ShopInventory dictionaries: 309 stock entries across 20 shops. It edits price modifier, purchase quantity, and available stock, repacks an isolated WGD project override, and reads the saved value back without changing gringores.rpf. The visible tab and one matching in-game shop still need confirmation.
