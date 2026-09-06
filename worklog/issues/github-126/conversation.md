# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356290016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126

Created: 2026-08-06T02:03:34Z; updated: 2026-09-05T06:56:14Z

Exact metadata: [source record](sources/issue-5356290016-b87817a43d287fc7a12a74ea99a502008b06afedb566eb674f730d3475df0cd0.json).

Doable? There's also like, a little icon next to the pickup popup in DS3 to indicate it went to overflow storage. Can we do that?
How would you even access this overflow storage? Not just codewise but UI-wise?

## issue 5356290016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126

Created: 2026-08-06T02:03:34Z; updated: 2026-09-06T13:07:10Z

Exact metadata: [source record](sources/issue-5356290016-11cfe5a291dc59ebde748eeef916d411e69fb1715d0e9422b2bbee8c676b01c8.json).

**Status: A Baked Beans prototype is installed, not general storage for every item.**

- [ ] On a spare save, buy or collect Baked Beans beyond the carry limit. Confirm only the excess goes to storage and a notice explains it.
- [ ] At a recognized camp, open F7 Overflow Storage. Deposit One and Withdraw One; confirm carried and stored counts change by exactly one without duplication.
- [ ] Save, quit and reload. Confirm stored beans persist and closing storage restores normal controls. Report the counts and failed step.

## issue 5356290016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126

Created: 2026-08-06T02:03:34Z; updated: 2026-09-06T13:57:30Z

Exact metadata: [source record](sources/issue-5356290016-de740cda505c72af62a58577465c116710af8930e833496e2be489a396f57ac8.json).

**Status: A Baked Beans prototype is installed, not general storage for every item.**

- [ ] On a spare save, buy or collect Baked Beans beyond the carry limit. Confirm only the excess goes to storage and a notice explains it.
- [ ] At a recognized camp, open F7 Overflow Storage. Deposit One and Withdraw One; confirm carried and stored counts change by exactly one without duplication.
- [ ] Save, quit and reload. Confirm stored beans persist and closing storage restores normal controls. Report the counts and failed step.

## comment 5550116464 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126#issuecomment-5550116464

Created: 2026-08-06T03:56:46Z; updated: 2026-08-06T03:56:46Z

Exact metadata: [source record](sources/comment-5550116464-f005e1c7efcc4c3e7e8fb9080eee2d9033c4471e917998f4726a718fca3ff2d1.json).

Research result: a real reserve is feasible, but not as a native satchel category or by watching rejected pickups. The viable design is to temporarily permit acquisition, observe the inventory delta, retain the active-cap amount, and persist excess in an ASI-owned reserve. Purchases, scripted grants, and pickups still need separate tests because their side effects may differ. The clean UI is a mod-owned Overflow Storage page opened at camp/locker; seamless vanilla-satchel insertion and a badge inside Rockstar's pickup feed remain unproven. Recommendation: prototype one ordinary provision end to end before calling it universal.

## comment 5550116483 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126#issuecomment-5550116483

Created: 2026-08-06T14:10:58Z; updated: 2026-08-06T14:10:58Z

Exact metadata: [source record](sources/comment-5550116483-9fda94cb40261dcd076f0187cbb0d90564a85f25fd3eef5561dbde2d4727d22e.json).

I don't understand. You're saying we should let them pick up things beyond the inventory limit, then take them away? But then won't they see the inventory acquisition/removal notifications? Is there any way to silence that?

## comment 5550116499 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126#issuecomment-5550116499

Created: 2026-08-09T07:37:03Z; updated: 2026-08-09T07:37:03Z

Exact metadata: [source record](sources/comment-5550116499-90f83c3021ea183958f4696cab2e50e75292e9c403364aebcbba90599f7cdf70.json).

Second-pass research answers the notification question:

Inventory mutation and feed notifications are separate. `simple_crafting.c:8605-8626` adds inventory through `INVENTORY::_0xCB5D11F9508A928D`; `simple_crafting.c:5378-5482` separately constructs/posts the pickup toast through `_UI_FEED_POST_SAMPLE_TOAST_RIGHT` (`0xB249EBCB30DD88E0`, resolved in `_downloads/natives.json:109287-109305`). Raw removal paths `_0xB4158C8C9A3B5DCE` and `_0x3E4E811480B3AE79` are used without feed calls at `simple_crafting.c:14076-14135`.

Therefore overflow can be silently removed/banked: the player keeps the original positive acquisition toast and may receive one explicit “sent to storage” toast, with no negative removal notification. Completely suppressing/replacing the original positive toast is not safely proven. `UI_FEED_CLEAR_CHANNEL` (`0xDD1232B332CBB9E7`) clears the entire Toast channel 6 and risks deleting unrelated notifications, so it is not a safe universal solution. Injecting a badge into a vanilla toast is also unproven because the ASI does not own its handle/payload.

A persistent reserve is feasible for ordinary stackable items. It cannot become a native satchel category through catalog data: `satchel_ui_event_handler.c:6814-6854` explicitly owns the fixed category list. A mod-owned camp/locker page is the clean access route. Prototype one ordinary provision class first; exclude currency, ammo, weapons, unique documents, and unique gear. Test loot, shops, crafting, and scripted grants separately because progression/mission side effects may occur before correction.

Required acceptance: active quantity stays capped, reserve gains exactly one, no removal toast appears, unrelated notifications survive, reserve persists/refills only after verified inventory change, and acquisition paths do not duplicate rewards or progression. No implementation or label change was made.

## comment 5550116518 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/126#issuecomment-5550116518

Created: 2026-08-11T09:45:14Z; updated: 2026-08-11T09:45:14Z

Exact metadata: [source record](sources/comment-5550116518-7d29c4edad6fe5014c8303c4d86e19a142a6738c4ff799f2fc35db050c92edff.json).

The first end-to-end prototype is installed for Baked Beans. Excess cans are removed only after a count readback and stored in a persistent reserve. At a recognized camp, press F7 to open Overflow Storage; it shows active and stored counts and has Withdraw One and Deposit One. The page pauses the hidden Story menus and waits for every input to be released before it accepts or returns input, so its controls cannot also craft or consume something underneath.

Please test buying or looting past the active cap, the storage notice, F7 deposit/withdrawal, save/reload persistence, and normal camp controls after closing the page. This is deliberately one provision first; it should expand only after this path proves safe in-game.
