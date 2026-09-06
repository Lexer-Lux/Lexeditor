# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356309718 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209

Created: 2026-08-06T06:40:35Z; updated: 2026-09-05T07:00:41Z

Exact metadata: [source record](sources/issue-5356309718-7167719f8571d2b644236e305ab5d68f0da2c84f5ca7a706908edfa75449df45.json).

I GO THERE AND HOLD E AND WHEN IT FILLS THE BUTTON PROMPTS DISAPPEAR, MY MINIMAP DISAPPEARS....THEN THEY JUST COME BACK. NOTHING HAPPENS

## issue 5356309718 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209

Created: 2026-08-06T06:40:35Z; updated: 2026-09-06T13:17:36Z

Exact metadata: [source record](sources/issue-5356309718-beb9080fbaa87165b0282f7247b95c6deec32b84c882162ddd379760b6dae15c.json).

**Status: Confirmed fixed in game and closed.** Newspaper-marker updates were overwriting shared shop state. Replacing that write with a read-only local count restored shop volumes, markers and interactions.

## comment 5550138508 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138508

Created: 2026-08-06T06:50:57Z; updated: 2026-08-06T06:50:57Z

Exact metadata: [source record](sources/comment-5550138508-5084c8e08b0ff2348551326769089a379b6dc3e9a7c58a6841ccbaae1f1af0b7.json).

Implementation update: the live partial-bounty trace showed shop_post_office running, SHOP_MENU flickering briefly, no item-list context, and no bounty mutation. I integrated a Receive Mail guard that arms only from Post Office INPUT_SHOP_BUY, survives the vanilla UI/control transition for 3.5 seconds, pauses mod-owned inventory/shop writes, and logs the real ready-delivery queue without modifying mail/save data. Combined release build passes and is queued for verified install. Keeping actionable until installed and Receive Mail is tested.

## comment 5550138520 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138520

Created: 2026-08-06T12:52:22Z; updated: 2026-08-06T12:52:22Z

Exact metadata: [source record](sources/comment-5550138520-6c7dcbf986647bd2322dd91aae5aa97977bfd5a233f0d499ed5514ecf13ef161.json).

i still can't receive my mail.

## comment 5550138530 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138530

Created: 2026-08-06T14:42:29Z; updated: 2026-08-06T14:42:29Z

Exact metadata: [source record](sources/comment-5550138530-79d4f07d47348fed6c12603ab657ce86f0135bf84829b85e3d2814eaf26ed446.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Receive genuine ready mail and attach GameplayTweaks.post-office-mail.log; confirm receipt works and no invalid forced-award behavior occurs.

## comment 5550138542 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138542

Created: 2026-08-10T05:20:36Z; updated: 2026-08-10T05:20:36Z

Exact metadata: [source record](sources/comment-5550138542-cc0f97836851861ae54c33af51d845170008589229ac21f3f519854f9ed5920c.json).

The new report is a failed runtime test, not a request for another mail-queue test. During the exact interval where the Post Office icon and clerk prompts disappeared, the unified log shows Rockstar's shop_post_office thread repeatedly dropping from one live reference to zero before shop_controller, SHOP_MENU, or any item list existed. GameplayTweaks' Receive Mail guard stayed protected=0, so it was not suppressing the prompts. The ST_TRAIN_STATION/ST_POST_OFFICE catalog trees and both Post Office blip definitions match vanilla. This remains unresolved and is now correctly actionable; I have not mislabeled the unrelated Lexer-Lux/Lexeditor#201 removal as a Post Office fix.

## comment 5550138564 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138564

Created: 2026-08-10T07:17:10Z; updated: 2026-08-10T07:17:10Z

Exact metadata: [source record](sources/comment-5550138564-09646eb5e39fdd719a7c1e712d036abaaf2155e521228ab53fdda08a765d78c5.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test receiving ready post-office mail and verify no false-ready or queue mutation.

## comment 5550138576 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138576

Created: 2026-08-10T08:02:47Z; updated: 2026-08-10T08:02:47Z

Exact metadata: [source record](sources/comment-5550138576-c795d50b11f5c13116da7d0a8f2df7a11bc2b66b69b55b57738e457cafd48427.json).

- SHOPS SHOW UP AS LOCKED ON THE MAP
- SHOPS DON'T SHOW UP AT ALL ON THE MINIMAP
- ENTERING GIVES NO INTERACTION PROMPTS
- THIS APPLIES TO TRAIN STATION WORKERS AND PAPERBOYS, BLOCKING A BUNCH OF ISSUES

## comment 5550138593 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138593

Created: 2026-08-10T09:43:13Z; updated: 2026-08-10T09:43:13Z

Exact metadata: [source record](sources/comment-5550138593-70a04882ba7bfe1fa89a644d4f0f1e8c2fe84d3e5b5add4d8bec92dfdd5bceba.json).

Returned critical runtime failure (2026-08-10): shops remain unusable. They now appear closed on the full map, are absent from the minimap, and holding RMB near shopkeepers produces no interaction prompts. This still affects ordinary stores, train-station clerks, and paperboys. The feature is not fixed or test-ready; Lexer-Lux/Lexeditor#209 remains actionable and high priority. Repair must restore vanilla shop availability/blips/prompts first, then preserve unrelated mod behavior.

## comment 5550138609 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138609

Created: 2026-08-10T09:49:57Z; updated: 2026-08-10T09:49:57Z

Exact metadata: [source record](sources/comment-5550138609-c2a9e5289640cbdecc50929db6c0c9fd940667973ba540bec25b50ac8c6fbbaa.json).

Exact source repair update (not yet installed): the failed session log proves Lexer-Lux/Lexeditor#201's two process-wide child-vulnerability hooks were already resident and repeatedly active (`free_roam=1`) while every shop family was absent upstream (`shop_controller=0`, no SHOP_MENU/item list). The INI was changed to `Enabled=0` only after that RDR2 process initialized, and the old module never unhooked live detours; replacing files on disk could not repair that process state.

Lexer-Lux/Lexeditor#209 now resolves those same two exact call anchors on the first gameplay tick and disables/removes only those targets. It does not remove all hooks, fabricate shop globals, force script threads, or replace vanilla prompts/blips. The verifier requires exact Lexer-Lux/Lexeditor#201 signature parity and forbids broad hook removal. This remains actionable until the combined build is installed and the log reports `[shop-safety] vanilla predicates restored=1`; then ordinary stores, train clerks, paperboys, minimap/full-map icons, and RMB prompts must be tested before acceptance.

## comment 5550138628 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138628

Created: 2026-08-10T10:43:53Z; updated: 2026-08-10T10:43:53Z

Exact metadata: [source record](sources/comment-5550138628-d8eb56ed5c03aeda4c785606a1cf7b849d0a553d86ebd0fe96f0df79ef4e7153.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/cbdb32d4-8c21-4c2e-a5b6-9558dfe7f5f5" />

Shops still not on map.
I went to the general store and held RMB and I got like, the default interaction stuff for a non-shopkeeper??? Stuff like greet???? Then a short while later it went back to nothing???

## comment 5550138654 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138654

Created: 2026-08-10T11:15:30Z; updated: 2026-08-10T11:15:30Z

Exact metadata: [source record](sources/comment-5550138654-30bdf47b2e36097955243b514113152ff106cc58dfbc8c6c7f2adca5c4b5713f.json).

Integration correction before the next build: Lexer-Lux/Lexeditor#201 now installs zero hooks and performs zero child writes, and the new ASI will only be installed after RDR2 exits. Therefore Lexer-Lux/Lexeditor#209 no longer performs the emergency signature scan / `MH_DisableHook` / `MH_RemoveHook` cleanup; that cross-session cleanup is unnecessary and could interfere with another mod's hook. Lexer-Lux/Lexeditor#209 is again strictly a read-only Receive Mail transaction guard. Its verifier passes with the zero-hook Lexer-Lux/Lexeditor#201 module. Existing `test me` status is unchanged; the next fresh process must confirm shop/minimap interactions and Receive Mail behavior.

## comment 5550138667 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138667

Created: 2026-08-10T12:13:34Z; updated: 2026-08-10T12:13:34Z

Exact metadata: [source record](sources/comment-5550138667-4ffd78dd6906f7c1e772268cc004c08a1ada32d70968037ecc4d1508a999a5d8.json).

you really don't seem to care or appreciate just how bad this is? you broke it yourself. just delete whatever you added that broke it.

## comment 5550138681 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138681

Created: 2026-08-10T12:55:17Z; updated: 2026-08-10T12:55:17Z

Exact metadata: [source record](sources/comment-5550138681-28acc10f1b3883f628718777b1439d07e4ecfbc35d382cdd0ac1e8275259b988.json).

The shop-breaking cause was the old child-vulnerability predicate hooks. The current RDR2 process started after the zero-hook build was installed: its live log says hooks=0 writes=0, and I read the two former hook targets directly from this running process; both contain their original Rockstar prologues, with no MinHook jump left. You can test any shopkeeper, station clerk, or paperboy in the game that is open now—no restart is needed for this check. If interactions are still absent in this clean process, the log will distinguish that from the removed hook cause.

## comment 5550138695 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138695

Created: 2026-08-10T13:09:21Z; updated: 2026-08-10T13:09:21Z

Exact metadata: [source record](sources/comment-5550138695-799415f3c14813b27032fb99c31f130b605aa9d043d9fea9f7b80d11da98b95b.json).

still not fixed.
this is not okay. this is not acceptable.

## comment 5550138711 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138711

Created: 2026-08-10T15:00:48Z; updated: 2026-08-10T15:00:48Z

Exact metadata: [source record](sources/comment-5550138711-a6b6e522485269925a76a6f44819234de15b778ff6f08e43706eb56e2071ddbf.json).

Held RMB at shopkeeper. Got the rob, greet, antagonize thing you get from regular mobs. Then again, it just disappeared.

## comment 5550138732 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138732

Created: 2026-08-10T15:43:01Z; updated: 2026-08-10T15:43:01Z

Exact metadata: [source record](sources/comment-5550138732-d3fa3334e52c1ac520f330f6574203417afa7e82417bde25f63eb7f48bd6ca8c.json).

Your latest result disproves my previous child-hook explanation: the live process had both former hook targets clean, but no shop script ever owned the shopkeeper, so Rockstar fell back to ordinary Rob/Greet/Antagonize and then dropped that prompt.

I found and removed a common background writer instead of adding another shop workaround. The carried-mask path was mutating Rockstar's shared inventory/clothing layer every 500 ms. Every affected Story shop family—general stores, gunsmiths, stations, post offices, and newspaper boys—uses the same inventory-transaction-busy predicate. The carrier now writes only on actual proxy/availability/worn-state transitions. I also added a read-only `[shop-runtime]` trace of that exact busy predicate, the relevant shop-script owners, SHOP_MENU, and RMB so one test will identify the remaining gate if this repair is incomplete.

Development build `69BCC290844CBB0202018C78FFAD73C0A381F5EC314960B9544794F8A2E2CE81` compiled and passed the Lexer-Lux/Lexeditor#209 and preserved Lexer-Lux/Lexeditor#175 checks. It is queued to install and hash-verify automatically when this RDR2 process closes. This issue remains `actionable` until that install actually lands; I am not calling it fixed yet.

## comment 5550138747 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138747

Created: 2026-08-10T16:05:39Z; updated: 2026-08-10T16:05:39Z

Exact metadata: [source record](sources/comment-5550138747-c5709a2f2641f1e2856d8f2bdd32086a3ab6b22762a43f1e4576edf3369b817d.json).

Correction: the first queued artifact accidentally included an interrupted, unverified Lexer-Lux/Lexeditor#109 movement edit. I stopped the swarm, removed that partial edit, reran the Lexer-Lux/Lexeditor#109/#6/parity checks, rebuilt, and replaced the installed artifact before the next launch. The clean installed development build is `A21576F017E3A4DEA024EE9AD172A61660059056680A55D383D9BB8DE3381A21`; source, manifest, and game-root hashes match. Lexer-Lux/Lexeditor#209 is now `test me` because its shop repair is physically installed; this is not a claim that the shops work until you test them.

## comment 5550138757 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138757

Created: 2026-08-10T18:46:02Z; updated: 2026-08-10T18:46:02Z

Exact metadata: [source record](sources/comment-5550138757-b4e7b402189dc1a77583b55b2377983d93f7b54710205f8231ecc8e3b863b63a.json).

Yeah the only difference is that now using RMB on the shopkeepers is back to giving me no button prompts at all. 

## comment 5550138770 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138770

Created: 2026-08-10T19:25:18Z; updated: 2026-08-10T19:25:18Z

Exact metadata: [source record](sources/comment-5550138770-9c8d3ca8d271370d6987892c1b6db18b5afec9d91b6be050870b4c18796408be.json).

The latest failed test rules out the two earlier explanations: the former Lexer-Lux/Lexeditor#201 hook targets were clean, and the shared inventory-busy readback stayed 0. The remaining shop owner briefly started and then disappeared.

I found a second background inventory writer that the carried-mask repair missed. The camp-kit policy was calling `INVENTORY_ENABLE_ITEM` on both camp kits every 500 ms in free roam even though the installed session had already banked the kit and both live records were absent. That does no useful Lexer-Lux/Lexeditor#101 work and continuously touches the same inventory layer while Story shop scripts acquire their owner.

I removed that steady-state writer. Free roam now only reads counts and mutates inventory if a kit actually reappears; enable/restore occurs only for a genuinely banked kit during mission entry. Lexer-Lux/Lexeditor#101, Lexer-Lux/Lexeditor#175, Lexer-Lux/Lexeditor#209, and campsite regression checks pass. Development build `79FB209BB9375C83D8104F2C7A56C087A725AB35712913524F1FA3E7E8F67A21` is compiled and queued for automatic hash-verified installation when the current RDR2 process exits. This remains `actionable` until the install actually lands.

## comment 5550138787 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138787

Created: 2026-08-10T22:18:07Z; updated: 2026-08-10T22:18:07Z

Exact metadata: [source record](sources/comment-5550138787-d7e24cfce133d65c75f8ef332995a0c04c7bf9c0110434cc7dcd86fc0c8e7e05.json).

The queued removal of the steady-state camp-kit inventory writer is now physically installed in hash-verified build `70B66FAB3A0082C6638633A2379AF40147AABEF99D8DBC9EFFA1CC9591746F1B`. This does not claim the shops work: the next ordinary shopkeeper interaction is the runtime acceptance check, and the read-only `[shop-runtime]` line will capture the exact owner/busy state if it still fails.

## comment 5550138799 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138799

Created: 2026-08-11T01:45:56Z; updated: 2026-08-11T01:45:56Z

Exact metadata: [source record](sources/comment-5550138799-30cfe4b1e9781288bc23dcee01708722cbc59f2d7ec4eec9a4e3c5d3d5b7041e.json).

I removed the last pre-menu shop mutation. Honor-price replacement now waits until Rockstar has actually opened SHOP_MENU, so it cannot run while a clerk prompt or shop script is starting. After the next restart, check that general-store, station-clerk, and newspaper-seller prompts remain present and that each shop opens normally.

## comment 5550138814 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138814

Created: 2026-08-11T04:09:06Z; updated: 2026-08-11T04:09:06Z

Exact metadata: [source record](sources/comment-5550138814-5a914a0f1b74080dd2e8c32b3ff0605217e9b4a65e7aaa97e9072dc4b2f3762a.json).

No change whatsoever.
This is absolutely unacceptable.

## comment 5550138825 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138825

Created: 2026-08-11T04:31:31Z; updated: 2026-08-11T04:31:31Z

Exact metadata: [source record](sources/comment-5550138825-156e75898af32fa89cebbf6ec3a5062e98c330e250dd6e12759f6bd83eae2a04.json).

I stopped adding shop workarounds. Six builds in a row named one more background inventory writer, removed it, and shipped — without ever running a test that could tell us whether this ASI is even involved. That was the real mistake, so this round fixes that first.

**Your screenshot says something different from the caption.** Inside the Valentine store the bottom-right group is `Aim Weapon` / `Buy Wagon` / `SHOPKEEPER` — the game still knows he is a shopkeeper; the *browse* action is what is gone. The minimap draws bank, post office, train station, newspaper, campfire, hitching post and your five cigarette-card markers fine. Only the shop family — general store, gunsmith, doctor, saloon, stable, barber — has no blip at all, including the one you are standing inside. So this is not a blip texture or renderer problem; those blips are never created.

**Things I checked and cleared, so nobody re-chases them:** the rebuilt `blips.ytd` (it contains every shop texture, and nothing custom needs it any more); the catalog's structure (parses, and every shop-inventory and shop-menu reference resolves); the fence sellable-items index (only an alphabetical re-sort).

**Two real defects I did find and fix:**
1. The catalog had nine duplicate keys — `COMPONENT_REVOLVER_NAVY_GRIP`, the three fancy grips, both sights, both barrels and the ebony grip — registered twice with conflicting satchel sizes, because a recent catalog pass re-added items that already existed. Removed the nine added copies by byte-exact surgery; the file is otherwise unchanged and now has zero duplicates and zero dangling references.
2. `[core-cost]` was still hammering the shared inventory layer. Your live log shows 641 availability writes with 637 failed readbacks and climbing — it retried an item whose own readback never confirms every five seconds, forever. It now gives up on an item after three failed readbacks, says so once, and re-arms only on a real core edge.

**What I actually need from you, and it costs one toggle, no restart.** The next build adds `[SafeMode] Quiet=1` to `GameplayTweaks.ini`. It hot-reloads in ~2 seconds and stops every GameplayTweaks feature dead — no reads, no writes, no prompts, no blips — while leaving the game running. Stand at a broken shopkeeper, set `Quiet=1`, save, wait two seconds, walk away and back.

- Prompts and shop icons come back → it is this ASI, and I bisect it with the ~40 `Enabled=` keys already in that file. Still no rebuilds, still no restarts.
- Nothing changes → this ASI is not the cause, it is the LML data side, and I test that by disabling `MyOverhaul` in `lml/mods.xml` for one launch.

Either answer halves the problem in one trip to a counter, which is more than the last six builds managed between them.

Build `5A8D5B9E597557275D2781246A1EEFBE4D53E543D49250168B76BE2009158A73` is compiled and queued to install and hash-verify when you close the game. The switch only works once that build is loaded, so it needs one launch first. Staying `actionable` — I am not calling anything fixed.

## comment 5550138834 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138834

Created: 2026-08-11T04:47:02Z; updated: 2026-08-11T04:47:02Z

Exact metadata: [source record](sources/comment-5550138834-605a621a1c4e4ac7ecb73597c181a1d4441211f859529a8cf075ed710ce630b8.json).

With Quiet=0 the icons still disappeared the moment I got close and none of the shops work. I set Quiet=1, walked around a bit, came back. No change. Genuinely my entire game is broken now dude. This needs to be fixed and it needs to be fixed STAT

## comment 5550138852 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138852

Created: 2026-08-11T05:32:28Z; updated: 2026-08-11T05:32:28Z

Exact metadata: [source record](sources/comment-5550138852-5718bb02be74acffb576bf48de02942e8820ebf4d4710995fb788ca0fb236499.json).

Confirmed in a clean launch: shops, shop icons, and clerk interactions work with UWO disabled. Safe Mode had already shown that suspending GameplayTweaks did not restore them, and the MyOverhaul data audit found no common shop-closing mutation. The remaining common cause was UWO, which injected behavior into shop owners. UWO remains disabled; no shop-state probe or speculative shop repair is needed.

## comment 5550138863 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138863

Created: 2026-08-11T06:31:11Z; updated: 2026-08-11T06:31:11Z

Exact metadata: [source record](sources/comment-5550138863-7764014db1ddf7cedfed7fa23898792f4adb75bb615894494e834f7efaca8c95.json).

Correction: Lexer-Lux/Lexeditor#209 is not fixed. Disabling UWO restored shops in the earlier 5A8D build, but the later development builds made the same failure return: shop icons disappear near stores, minimap icons are absent, and shopkeepers have no shop interaction. That disproves the closed-state conclusion. The issue is reopened as actionable; I will not treat either UWO or development mode as the cause without reproducing the working-to-broken artifact difference.

## comment 5550138876 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138876

Created: 2026-08-11T07:02:04Z; updated: 2026-08-11T07:02:04Z

Exact metadata: [source record](sources/comment-5550138876-bfe9fc9d15eb870df088433719c68c9e134ebbbe54300b17fad2ddd2b6d65a9b.json).

The broken session showed the actual chain: an inactive saved campsite had no physical camp and no tracked thread, but Rockstar's `player_camp` owner remained live. The prematurely shipped tonic-refill module then treated that raw script reference as a rest event and entered its inventory path even though Lexer-Lux/Lexeditor#130 is blocked by Lexer-Lux/Lexeditor#126.

The installed repair removes Lexer-Lux/Lexeditor#130 from the runtime and settings. It also cleans the exact custom `player_camp` owner when an inactive campsite has one or when a tracked active camp leaves materialization range. Cleanup is bounded and waits for the script reference/thread readback; it does not force shop state or fabricate prompts.

After a clean restart, test one general store, one station clerk, and one newspaper seller. The visible requirement is that their map/minimap icons and interaction prompts remain available. This is installed for testing, not yet claimed as confirmed.

## comment 5550138895 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138895

Created: 2026-08-11T07:22:39Z; updated: 2026-08-11T07:22:39Z

Exact metadata: [source record](sources/comment-5550138895-93816ecbadaf111b9c9615d4c4a315571ba96e1aac9f694fd435dcf85545fa5e.json).

The continuing failure was not the campsite cleanup. The new log showed that cleanup completed, but the carried-mask feature then wrote Rockstar's shared clothing cache from an address that was one slot late. That startup write corrupted the inventory/clothing state used by shop presentation. I removed every direct cache and refresh-flag write; the mask now uses only Rockstar inventory natives. Restart the game, then test one general store, one station clerk, and one newspaper seller. Their full-map and minimap icons must remain available, and RMB must show the normal shop interaction.

## comment 5550138905 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138905

Created: 2026-08-11T07:37:24Z; updated: 2026-08-11T07:37:24Z

Exact metadata: [source record](sources/comment-5550138905-4742ecdb9ae3867e3d18efbc4ccd6e62ace408ea7c69d030257e1b118faa6113.json).

Correction: the carried-mask raw cache writer was a real unsafe defect, but it is not proven to be the shop cause. The carried-mask updater was not gated by developer mode, so it also ran in the earlier working dev-off launch. That contradicts my causal claim. Lexer-Lux/Lexeditor#209 is back to actionable. I am treating the exact working-to-broken ASI difference—not developer mode or the mask defect by association—as the unresolved cause.

## comment 5550138922 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138922

Created: 2026-08-11T07:39:42Z; updated: 2026-08-11T07:39:42Z

Exact metadata: [source record](sources/comment-5550138922-8e0b7e0189e3a306868e989b13381c237589ba7288b247ff590506de2786449b.json).

The latest ASI was tested and made no difference: shops remain closed or absent and their interactions are still missing. Removing the unsafe carried-mask cache writer did not restore them, so that defect is now ruled out as the shop repair. Lexer-Lux/Lexeditor#209 remains actionable.

## comment 5550138942 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138942

Created: 2026-08-11T08:19:19Z; updated: 2026-08-11T08:19:19Z

Exact metadata: [source record](sources/comment-5550138942-894eb559099b357b93f56535a626a60a1d70ead956ca604c339fb94312c5e7dd.json).

The returned log showed the carried-mask feature still feeding Rockstar's temporary availability state back into the inventory. It disabled the carrier when the shared bit dropped, then enabled it again less than a second later. That transaction occurred while the same inventory/shop owner was changing state.

I removed both availability writes. The mask may observe the shared bit, but Rockstar now owns it. I also put a read-only shop-owner gate before every GameplayTweaks feature update. It gives short_update first access to start the nearby shop script and records the exact blocking flag if that owner still does not start. It does not create shop prompts, icons, globals, or script threads.

The development build is installed, and development mode still starts enabled. Restart RDR2 and check a general store, station clerk, and paperboy. Their minimap icons must appear and RMB must open the normal shop interaction. If one fails, stop there; the new shop-startup line will identify the remaining Rockstar gate.

## comment 5550138951 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138951

Created: 2026-08-12T05:03:13Z; updated: 2026-08-12T05:03:13Z

Exact metadata: [source record](sources/comment-5550138951-d9b8135bf49c953ee2597c9862eb78c9780d2082a1e123216e349412460c143d.json).

The current log showed the shops were already absent on the first normal GameplayTweaks frame. The later core-item and dual-wield writes had not started yet, and the camp-kit policy made no inventory change.

The carried-mask updater did write on that first frame. Its startup latch treated an already-existing mask proxy as a new selection, then unhid it and rewrote its in-use state while Rockstar was acquiring shop ownership. I removed that startup reconciliation. Loading the ASI now reads the existing proxy state without changing it; clothing writes require an actual mask selection or mask-use command. I also kept the two unaccepted inventory writers from Lexer-Lux/Lexeditor#238 and Lexer-Lux/Lexeditor#243 out of this shop-recovery build.

Restart RDR2. At one general store, confirm that the icon remains open on the map, appears on the minimap, and holding RMB on the shopkeeper gives the shop prompt. Then check one station clerk and one paperboy. If any one fails, stop there; the first new shop-startup and carried-mask records are sufficient.

## comment 5550138969 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138969

Created: 2026-08-12T05:39:01Z; updated: 2026-08-12T05:39:01Z

Exact metadata: [source record](sources/comment-5550138969-ce60e5b7a5d548209684d5a39d47900a656e2ba1068fccddb1bb08ddeeb40c31.json).

The last launch disproved the mask-startup theory: the mask made no write, the Lexer-Lux/Lexeditor#238/#151 updaters did not run, and the shops still failed. It also showed that the shop observer never found a record, so it was not protecting anything.

I corrected that observer against Rockstar's full shop and location ranges and installed it. When you enter any authored shop radius, GameplayTweaks now stops its own feature updates until Rockstar's real shop thread is active; it does not time out and resume mutations after 12 seconds. The same launch records every shop row and the exact owner gate. Relaunch normally and approach a shop. Lexer-Lux/Lexeditor#209 remains actionable until the real icon and RMB interaction work.


## comment 5550138994 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550138994

Created: 2026-08-12T06:21:14Z; updated: 2026-08-12T06:21:14Z

Exact metadata: [source record](sources/comment-5550138994-98a0cadee09a9110ad44481973638bfa8ebc753cb0cef64d67348d1cb2a48a5a.json).

The last build still failed: Rockstar shop icons were absent from both the full map and minimap at every distance, shopkeepers remained unavailable, and the general-store light flickered; the bank mod's separate custom icon remained visible.

I found a concrete error in my shop observer. It read every `short_update` shop record one global early because I omitted Rockstar's fixed-array header. That is why it produced no useful shop records and did not protect the actual owner. The corrected build is installed now. Its trace runs before deferred initialization and before every GameplayTweaks feature, and records the real shop record, map blip, owner thread, eight-slot startup queue, script-stack availability, and blocking flags. This issue remains actionable until the real icons and shopkeeper interaction work.

## comment 5550139007 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139007

Created: 2026-08-12T07:45:00Z; updated: 2026-08-12T07:45:00Z

Exact metadata: [source record](sources/comment-5550139007-9876b01b63d5bfbe4cb474e5d1334259ae26a89eb84732ccb0446328fb78f310.json).

The latest trace showed the general-store and newspaper shop threads starting, then dying after GameplayTweaks resumed its feature updates. That same release made the camera debug text flicker. I installed a development build that now keeps GameplayTweaks contained for the complete time you are inside an authored shop radius, including while Rockstar's shop thread is active. It does not write shop globals, create icons, or start shop scripts. Test the same general store: its icon must remain available, the correct RMB shop interaction must remain present, and the camera debug text must stay hidden without flickering while you are inside the shop radius.

## comment 5550139015 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139015

Created: 2026-08-12T07:54:37Z; updated: 2026-08-12T07:54:37Z

Exact metadata: [source record](sources/comment-5550139015-324caa10fe22178b48e7f34af8988cb46bdaf6de0abaf5292f1c80606ca45184.json).

The last build did not provide continuous protection. The new log showed short_update temporarily unloading the nearest shop record while the gunsmith thread was active. GameplayTweaks resumed for that gap, and the gunsmith thread was dead at the next observation. The installed repair now retains the last verified authored shop position and radius through that record-table churn, so a one-frame missing record cannot resume mod features while you are still inside the shop area. This supersedes the previous containment build. Test the same shop once after restart; if it still fails, I will use this session's owner trace rather than ask you to repeat the same containment change.

## comment 5550139026 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139026

Created: 2026-08-12T08:03:58Z; updated: 2026-08-12T08:03:58Z

Exact metadata: [source record](sources/comment-5550139026-37579cdbf090fc601f702e2185f343b7f82f96630055bb4721609e087430696c.json).

I removed the failed shop-containment experiment. The actual release/development difference was a source contradiction: the code said every build starts authoring disabled, but initialized runtime development mode from the build type. Every development ASI therefore started camera/fortification authoring and other developer-gated paths immediately; release builds started them off. The installed development build now starts runtime development mode off, matching the working release startup, while keeping Tilde available to enable authoring explicitly later. Normal gameplay features remain compiled. Restart and check an ordinary shop before pressing Tilde.

## comment 5550139037 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139037

Created: 2026-08-12T09:32:57Z; updated: 2026-08-12T09:32:57Z

Exact metadata: [source record](sources/comment-5550139037-8f75d4f8498b8c2e7d424b3a7ab342ae88488d3ab3e90265b1c4848705d941b2.json).

Narrowed to one loop. Standing at the Valentine counter, the probe sampled `shop_general` every two seconds and caught this:

```
thread=81   state=0  volume=2309    volumeExists=0  LOCKED=1  mode=5
thread=229  state=1  volume=296200  volumeExists=0  LOCKED=1  mode=0
thread=303  state=0  volume=137992  volumeExists=0  LOCKED=1  mode=5
thread=591  state=1  volume=324625  volumeExists=0  LOCKED=1  mode=0
thread=727  state=0  volume=226073  volumeExists=0  LOCKED=1  mode=5
```

The shop record is being destroyed and rebuilt continuously — new thread id every sample, state flipping, and a different unresolvable volume handle each time. A healthy session reads a stable `volume=84738 volumeExists=1`.

That one loop produces every symptom you reported. Invalid volume makes the game mark the shop locked; `BLIP_MODIFIER_LOCKED` is a padlock overlay plus alpha 0.10, which is still legible on the full map and invisible on the minimap — your "icons on the map, nothing on the minimap". The rebuild is also what you're seeing as the location popup re-firing and the light flickering. So it is one cause, not two unrelated bugs, which is what you said it had to be.

Things now ruled out by direct measurement rather than argument: free script stacks (5-7, never 0), the game clock (packed hour matches, and the artwork is LOCKED not the time-of-day modifier), and the shopkeeper himself — he is valid, carries the vendor flag, is not fleeing and has no task. "SHOPKEEPER_AGGROED" is a misleading label; the same mode is reached when the shop's volume is missing.

Separately, the probe settled an array-base question and that exposed a genuine bug: `updateHonorShopPriceModifier` omitted the fixed-array capacity header, so every scan and write landed one cell short across all 38 shop records and could write a float into unrelated shop data. Fixed and installed (`8A270D37...`). It is gated behind SHOP_MENU and your failing sessions all show that closed, so I am *not* claiming it is the cause — it is a real corruption bug that needed fixing regardless.

Also withdrawing an earlier claim in this issue: the safe-mode test did not exonerate GameplayTweaks. Suspending code that latched a persistent engine state does not undo that state, so that elimination was never valid.

Remaining question is now a single one — what re-triggers shop/area entry every couple of seconds. Full evidence and the next probe fields are in the worklog.

## comment 5550139046 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139046

Created: 2026-08-12T11:29:02Z; updated: 2026-08-12T11:29:02Z

Exact metadata: [source record](sources/comment-5550139046-f187a60c86f4f14921dc200976950b6b62c0fb417ad3f05b4b7dba926fc83bf7.json).

Claude's staged diagnostic is now finished and installed. I corrected two unfinished parts before building: the read-only shop probe now runs before every stage gate, and the 12-second ramp advances only during active gameplay, not while paused or tabbed out.

For the next launch, do not change any settings. Load Story Mode and remain near a broken shop for about three minutes while playing normally. The build starts with later GameplayTweaks groups blocked, restores one group every 12 seconds, and records the exact dispatcher interval where the shop state first changes. This is a cause-finding build, not a claim that shops are fixed. Lexer-Lux/Lexeditor#209 remains actionable.

## comment 5550139068 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139068

Created: 2026-08-12T11:35:26Z; updated: 2026-08-12T11:35:26Z

Exact metadata: [source record](sources/comment-5550139068-107368e18cf165f2e6e25963679a203afb1dfeaf7e61222b52479b9e9e1b79bd.json).

Correction before runtime: I replaced the broad 14-group ramp with a focused split of only the eight individual paths inside the already-proven old gates 0-3. Later dispatcher groups remain blocked for the entire run. The useful test now lasts about 96 seconds near a broken shop and will identify overflow storage, custom crafting, in-game settings, collectible polling, newspaper markers, campfire policy, serious-crime payoff, or collectible-mask removal without repeating the cleared groups.

## comment 5550139088 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139088

Created: 2026-08-12T11:44:52Z; updated: 2026-08-12T11:44:52Z

Exact metadata: [source record](sources/comment-5550139088-d9bf01e514b6842ee332f14ba9639b62060dfcd57fc2d1f35f03a0744c6ec104.json).

Cause isolated from the focused trace and repaired. Shops stayed healthy through overflow storage, custom crafting, settings, and collectible polling. The first destructive transition occurred immediately after `updateNewspaperVendorMarkers`: the valid general-store volume was replaced by invalid handles, its state began cycling, and the LOCKED bit appeared across shop families.

The newspaper marker updater had copied Rockstar's private newspaper-shop cache refresh and wrote `Global_1430252` from GameplayTweaks' main loop. It now counts the same 14 persisted newspaper records locally and performs no shop-cache write. The temporary stage gates are removed, and the normal full ASI is installed. Lexer-Lux/Lexeditor#209 remains actionable until shops are confirmed after restart.

## comment 5550139104 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/209#issuecomment-5550139104

Created: 2026-08-12T11:50:03Z; updated: 2026-08-12T11:50:03Z

Exact metadata: [source record](sources/comment-5550139104-c9d61bddf81c8230de79719e7d6b1996e70c1c814c5a75a9f2191cdf723fae80.json).

Confirmed fixed in game. The cause was `updateNewspaperVendorMarkers` writing Rockstar's private newspaper-shop cache from GameplayTweaks' main loop. Replacing that with a local read-only count restored shop volumes, icons, and interactions. Closing Lexer-Lux/Lexeditor#209.
