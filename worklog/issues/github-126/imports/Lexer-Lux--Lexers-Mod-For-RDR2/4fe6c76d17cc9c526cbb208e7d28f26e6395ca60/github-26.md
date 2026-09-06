# GitHub #26 - DS3-Style Overflow Storage

## Failure classes checked before implementation

- A rejected pickup could not be treated as acquired inventory. The prototype first raised one proven catalog cap and then required a positive live inventory delta.
- A native return value or call-site log could not prove a transfer. Both removal and rollback used inventory-count postconditions.
- The raised engine cap could not become the player's active cap. The module recovered the authored cap from Rockstar's live role-max result by subtracting the exact catalog lift.
- A polling loop could not fight inventory every frame. The observer ran every 250 ms and mutated only on initialization or a count transition.
- Storage could not claim an amount that failed to persist. The reserve changed only after verified removal and a successful persistence write. A failed write attempted a verified inventory rollback and disabled the prototype.
- The prototype could not include currency, ammunition, weapons, documents, unique gear, or other unproved item classes.
- A one-way reserve was not usable storage. The module could not be registered until a withdrawal route existed.
- A mod page could not pass its accept/cancel inputs into Rockstar's camp or crafting owners. Input ownership required balanced Story-native thread isolation, all-control suppression, release-gated handoff, and a dispatcher-visible ownership return.

## Primary evidence

- `datasets/vanilla/catalog_sp.ymt`, top-level `CONSUMABLE_BAKED_BEANS_CAN`: the item was an ordinary `CI_CATEGORY_PROVISION` / `CONSUMABLE` item with consumable and provision tags. Its vanilla base `SLOTID_SATCHEL` multiplicity was 3.
- `MyOverhaul/catalog_sp.ymt`, the same record: the authored mod base `SLOTID_SATCHEL` multiplicity was 1, the next satchel contribution was 1, and the Legend of the East contribution was 994. The prototype therefore had to preserve a live cap of 1, 2, or 995 rather than invent one fixed player cap.
- `_downloads/natives.json`: `0xE80E50BEE276A54A` was `_GET_ITEM_SLOT_MAX_COUNT`; `0xADDD1E7C0ECF7D95` was `_GET_ITEM_ROLE_MAX_LEVEL_COUNT`.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/simple_crafting.c`, `func_147`, `func_192`, and `func_233`: Story used inventory 1, queried the slot or current role maximum, and acquired through `_INVENTORY_ADD_ITEM_WITH_GUID`.
- The same script, the item-feed wrapper near `func_164`: acquisition UI used `_UI_FEED_POST_SAMPLE_TOAST_RIGHT` separately from inventory mutation.
- The same script, `func_381`: raw `_INVENTORY_REMOVE_INVENTORY_ITEM_WITH_ITEMID` took a reason and did not post a feed. This allowed the original positive acquisition notification to remain while the mod posted one separate storage notification.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/satchel_ui_event_handler.c`, `func_208`: the native satchel navigation had a fixed category list and no overflow category. A native storage tab was not assumed.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/player_camp.c`, the prompt setup around line 14751, and `interactive_campfire.c`, the parallel setup around line 5463: Rockstar exposed satchel access only while its camp owners were active. These script names supplied the page's camp boundary.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/camera_photomode.c`, `func_29`, and `camera_item.c`, `func_59`: Rockstar acquired exclusive modal ownership with balanced `_PAUSE_SCRIPT_THREADS(true/false)`, prompt type 6, render freeze/restore, and photo-mode defreeze. The mod page used that same ownership lifecycle.
- `GameplayTweaks/modules/custom_crafting.cpp`: the existing custom page kept Story threads paused until owned inputs were released, disabled the underlying controls every frame, and returned an ownership state to the integration dispatcher. The overflow page followed that established isolation rule without changing the crafting owner.
- `GameplayTweaks/modules/settings_menu.cpp`: the existing mod-owned renderer used Rockstar texture dictionaries, draw order 7, disabled frontend/game-menu controls, and explicit selection/accept/cancel handling. The overflow page used a separate issue-owned renderer and did not add transaction actions to the settings editor.

## Implemented prototype

- Added `GameplayTweaks/overflow_storage_items.csv` with one item: baked beans, authored base 1, lifted base 99.
- Added `tools/reverse-engineering/apply_overflow_storage_issue_26.py`. It found the one top-level item record and changed only its `SLOTID_SATCHEL` quantity. It refused any unexpected source value.
- Added `GameplayTweaks/modules/overflow_storage.cpp` as an unregistered issue-owned module.
- The module first read the explicit engine base contribution and refused inventory writes unless it equaled 99.
- It read Rockstar's live role maximum and subtracted the exact 98-item lift. This preserved the authored active maximum for the player's current satchel upgrade.
- It observed one count every 250 ms. On initialization or a positive count transition above the recovered active maximum, it removed only the excess.
- It read the count again, persisted only `before - after`, and posted one explicit overflow-storage card. A persistence failure attempted to restore the verified removed amount and disabled further transactions.
- Reserve state used `GameplayTweaks.overflow-storage.ini`. Heartbeats reported count, engine cap, recovered active cap, reserve, and whether the catalog lift was active.
- Added a mod-owned camp page. `F7` opened it only while `player_camp`, `interactive_campfire`, `campfire_gang`, or `campfire_gang_es` was running, and not over a crafting, satchel, or pause page.
- The camp page displayed the one prototype item's active count, recovered active cap, and persisted reserve. It offered `Withdraw One` and `Deposit One`. Keyboard arrows/Enter/Escape and controller navigation/accept/cancel worked after the page opened.
- Deposit and withdrawal each used before/after inventory readbacks and persisted only the observed delta. A failed persistence write used the inverse inventory operation, verified that rollback, disabled further transactions, and did not claim success.
- The page paused all other Story script threads, suppressed all three control groups, did not arm input until all owned keys/buttons were released, and did not resume Story until the closing input was released. It used Rockstar's matching photo-mode defreeze/render restoration on release.
- `updateOverflowStorage(now)` returned `true` while the page owned input. This let the integration dispatcher skip later mod hotkey handlers in the same caller thread; pausing other Story threads alone could not isolate those same-thread handlers.

## Static proof

- `python tools/reverse-engineering/verify_overflow_storage_issue_26.py` mechanically applied the catalog patch to a temporary copy and confirmed that no other line changed.
- The verifier checked the ordinary-provision evidence, both max-count readbacks, catalog-lift gate, derived active cap, transition-only mutation, deposit and withdrawal readbacks, both persistence rollback paths, storage feed, heartbeat, camp boundary, balanced Story-thread isolation, all-control suppression, release gating, draw ownership, and the named Story sources.

## Integration requirements

- The integration agent must run `python tools/reverse-engineering/apply_overflow_storage_issue_26.py --apply` against the shared `MyOverhaul/catalog_sp.ymt` and reconcile that one shared record with concurrent catalog work.
- It must include `modules/overflow_storage.cpp` after the existing feed helper.
- It must call `updateOverflowStorage(now)` before later mod menu/hotkey handlers, use the returned ownership value to skip those handlers for that frame, and decline to open this page while another mod-owned page has input. This dispatcher reconciliation is integration-owned.
- It must package `overflow_storage_items.csv` beside the ASI.
- It must compile, install, hash-verify, and keep #26 `actionable`.

## Exact boundary and runtime acceptance

This remained a one-item transaction and UI prototype, not the complete issue. It did not generalize the proved flow beyond baked beans and did not inject a category into Rockstar's fixed satchel navigation. The separate mod-owned camp page supplied both deposit and retrieval without taking ownership of the vanilla satchel app.

Visible acceptance for the prototype remained in-game:

1. Start with the current baked-beans active maximum and acquire one more through a normal world, loot, shop, or crafting path that the lifted catalog now permits.
2. Confirm the original acquisition notification still appears once.
3. Confirm the active count returns to the exact pre-lift maximum and one separate storage notification appears.
4. At a normal portable camp, confirm the `F7 Overflow Storage` hint appears. Open it and confirm active/stored counts match the transaction.
5. Withdraw one. Confirm the active count increases by one, stored count decreases by one, and no unrelated camp action occurs.
6. Deposit one. Confirm the inverse exact changes and no unrelated camp action occurs.
7. Close with Escape or F7, release the key, and confirm the normal camp controls resume once without a delayed satchel/craft action.
8. Restart the game and confirm the page and heartbeat report the same reserve.
9. Confirm unrelated notifications remain and no removal notification appears.

#26 had to remain `actionable` because only one ordinary provision was implemented and the camp page, isolation, persistence, and acquisition paths still required in-game acceptance.
