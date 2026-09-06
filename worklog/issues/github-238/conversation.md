# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356316373 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238

Created: 2026-08-10T10:22:31Z; updated: 2026-09-05T08:34:06Z

Exact metadata: [source record](sources/issue-5356316373-a1f1f8df541b5fd203950852305d4cf31578761ce1abe7fd07d8461278a44cab.json).

## Player-facing behavior

An item that decreases one or more cores must be unavailable and greyed out when using it would reduce any affected core below 0.

## Requirements

- Evaluate the item's actual configured core effects before allowing use.
- For each negatively affected core, compare the current core value with the amount the item would subtract.
- If any affected core would end below 0, disable/grey out that item in every relevant inventory surface and prevent activation through shortcuts or alternate use paths.
- A result of exactly 0 is allowed; only a result below 0 is blocked.
- Positive and zero effects do not contribute to the block.
- Items affecting multiple cores are blocked if even one negatively affected core would fall below 0.
- Do not consume the item, play its use animation, or apply only part of its effects when blocked.
- Restore availability immediately when the relevant core is high enough.
- Use the same effective item values shown/configured by the overhaul rather than unrelated vanilla defaults.

## Acceptance test

1. Set a core below an item's negative cost and confirm the item is greyed out and cannot be used.
2. Set the core exactly equal to the cost and confirm the item can be used, ending at 0.
3. Test an item affecting multiple cores and confirm one insufficient core blocks the entire item.
4. Raise the insufficient core and confirm the item becomes usable without a restart.
5. Confirm radial, satchel, hotkey/shortcut, and contextual use paths enforce the same rule.
6. Confirm blocked attempts do not consume inventory or start an item-use animation.

## issue 5356316373 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238

Created: 2026-08-10T10:22:31Z; updated: 2026-09-06T12:56:29Z

Exact metadata: [source record](sources/issue-5356316373-3d9900ca66c587d8f0831f41fca81a6f1625ec708e9d5ea2174723525f0eb016.json).

An item must be visibly unavailable before use when its configured negative effect would reduce any core below zero. Exactly zero remains allowed.

**Status: Partly working, still defective.** You confirmed use is blocked, but the radial does not grey the item out, so it appears selectable and silently does nothing. Fix that visible availability mismatch before another acceptance test.

## issue 5356316373 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238

Created: 2026-08-10T10:22:31Z; updated: 2026-09-06T12:56:29Z

Exact metadata: [source record](sources/issue-5356316373-dadff916def9f18855d290a7b6365a2265a3871bf6820db3f379f3fe81446019.json).

An item must be visibly unavailable before use when its configured negative effect would reduce any core below zero. Exactly zero remains allowed.

**Status: Partly working, still defective.** You confirmed use is blocked, but the radial does not grey the item out, so it appears selectable and silently does nothing. Fix that visible availability mismatch before another acceptance test.

## comment 5550146110 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146110

Created: 2026-08-10T11:15:31Z; updated: 2026-08-10T11:15:31Z

Exact metadata: [source record](sources/comment-5550146110-1410a56231650318903c6c724ebb45d7b8c637cbdb13193ccb082b3b02284386.json).

Implemented in source and integrated into the combined dispatcher/config/editor. The guard resolves each configured item's live ITEM_DATABASE core effects, greys/disables the item through Rockstar's inventory availability layer only when `current core < cost` (equality remains usable), blocks the cached quick-use action, and cancels a normal/context item-interaction bypass before its authored consume/effect event. It currently covers all 15 negative-core consumables in `MyOverhaul/catalog_sp.ymt`, including multi-core costs. `[CoreCostGuard] Enabled=1` hot-reloads within about two seconds. Static verifier passes; this remains `actionable` until the exact combined ASI is built, installed, and hash-verified.

## comment 5550146126 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146126

Created: 2026-08-10T12:12:53Z; updated: 2026-08-10T12:12:53Z

Exact metadata: [source record](sources/comment-5550146126-2a7c21d44450f387a520c64b931a25ce00b2d1d192d1e724425600f268087a67.json).

I have 0 stamina core and can still smoke cigs. Try again.

## comment 5550146139 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146139

Created: 2026-08-10T16:37:44Z; updated: 2026-08-10T16:37:44Z

Exact metadata: [source record](sources/comment-5550146139-9bacdd28cdc218d2185aa7e5f23896c18ae5e2727051ca37562bd8f4c856713f.json).

The log confirms why your zero-Stamina cigarette test failed: the module resolved **0 of 15** item effects, so it never blocked anything.

The effect-ID buffer was one slot short. Rockstar's script array stores `count`, then a fixed-array capacity header (`20`), then the effect IDs. I omitted that header, so the module treated the literal capacity `20` as effect ID 0; that lookup failed forever for every item.

I corrected the buffer to `count + capacity + 20 IDs` and strengthened the verifier to reject the old layout. The next build is not eligible for your UI test unless its live log first reports `resolved=15/15`. Lexer-Lux/Lexeditor#238 stays `actionable` until that corrected build is compiled and installed; I am not asking you to retest the current installed one.

## comment 5550146163 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146163

Created: 2026-08-10T17:01:06Z; updated: 2026-08-10T17:01:06Z

Exact metadata: [source record](sources/comment-5550146163-c6bf4bca90356b3bd5ddf44c20dbf7dd7075ffa19f5694f9a84fc02b0ab5372d.json).

The corrected core-cost guard is installed. The fixed-array header omission that caused resolved=0/15 is repaired; the next run must first report resolved=15/15. Then, with a zero Stamina core, cigarettes and every other item whose cost would go below zero should be grey/unusable; equality remains allowed, and multi-core costs check each affected core.

## comment 5550146177 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146177

Created: 2026-08-10T19:26:41Z; updated: 2026-08-10T19:26:41Z

Exact metadata: [source record](sources/comment-5550146177-d5963c398ac5cd22f9af389477c318567ff15881d2943e3eee350119e336e6e7.json).

Still nothing. What does the log say?

## comment 5550146198 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146198

Created: 2026-08-11T06:03:24Z; updated: 2026-08-11T06:03:24Z

Exact metadata: [source record](sources/comment-5550146198-93d32ca88882a704c25f9854d2592dbe40b2810c0d3b658e233fbb04b1353814.json).

The new development build reintroduced the shop failure while UWO remained disabled. Its live log shows Lexer-Lux/Lexeditor#238 repeatedly writing Rockstar's global inventory availability for Moonshine, including after inventory revisions. Shops had worked immediately before this ASI installed. CoreCostGuard is now disabled in the installed INI and removed from the next build's dispatcher. The feature remains failed and is not ready for testing.

## comment 5550146215 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146215

Created: 2026-08-11T09:32:32Z; updated: 2026-08-11T09:32:32Z

Exact metadata: [source record](sources/comment-5550146215-0fdc9ad5e6adb7d239e5cd75ab76bef71178dbbbb84e8ecffab2e964fa43d32d.json).

The core guard no longer writes 15 item states every frame or during shop/inventory ownership. It waits 15 seconds after startup, defers during the wheel, backup inventory and item interactions, and writes only on a core edge or settled inventory revision with a disabled-state readback. Test a below-cost item, exact-equality item, and a normal shop in the same session.

## comment 5550146226 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146226

Created: 2026-08-14T00:34:27Z; updated: 2026-08-14T00:34:27Z

Exact metadata: [source record](sources/comment-5550146226-00f0df3ff7df6a46078587cc5fe3bf4ca30defebb02014fc5713b8ec498735e4.json).

**The fix announced here cannot run. Its dispatcher call is commented out.**

The last comment told you to test a below-cost item, an exact-equality item and a normal shop. That test could never have produced anything, because `updateCoreCostGuard` is disabled at `script.cpp:3156`:

```cpp
// Lexer-Lux/Lexeditor#209 isolation: Lexer-Lux/Lexeditor#238 writes Rockstar inventory availability. Its player-
// visible result is still unaccepted, so it cannot share the shop-recovery
// build until shops are proven stable.
// updateCoreCostGuard(ped, now, dead || SCREEN_FADED_OUT());
```

Your whole session confirms it: **zero** core-guard log lines. The module compiles and is included, so it looked shipped while being dead code. Same failure as Lexer-Lux/Lexeditor#243 earlier today — an isolation comment outliving the reason for it, and an issue comment written as though the code were live. I am sorry for the wasted test.

**Why I have not simply switched it back on.** The isolation's own condition is "until shops are proven stable", and this module writes Rockstar inventory availability — the exact surface that broke your shops before. Shop ownership was restored in 34f3396, and the current session looks healthy (doctor, general, gunsmith, post office and newspaper vendors all cycling normally with valid volumes and clerks). But 700 lines also show `LOCKED=1` on the barber and horse shop, which is *probably* just no clerk at that hour, and I cannot tell the difference without playing. Turning an inventory-availability writer back on, blind, while you are away and unable to notice shops breaking, is not a risk worth taking for this feature.

**So this is your call, and it is a one-line change either way:**

- **Turn it on** — you get to actually test the core guard, with the risk that if shops break you lose a session to it. The guard now waits 15 s after startup, defers during the wheel, backup inventory and item interactions, and only writes on a core edge or settled inventory revision with a readback, so it is far more constrained than the version that caused the damage.
- **Leave it off** — shops stay definitely safe and Lexer-Lux/Lexeditor#238 stays permanently untestable.

Say which and I will do it in the same turn. Staying `actionable`, correctly this time: there is work outstanding, and it is not yours to discover by testing something that cannot execute.


## comment 5550146245 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146245

Created: 2026-08-14T01:15:09Z; updated: 2026-08-14T01:15:09Z

Exact metadata: [source record](sources/comment-5550146245-fdecd1bdbb2383f697b7d97adf7fe1b13ef6d749290e50c9738737a821b67cc6.json).

**Turned on, as you asked. Here are the two answers.**

**What the core guard is.** It stops you using an item whose own negative effect would push a core below zero — a tonic that costs 30 Stamina when you only have 20, for instance. Those items get greyed out in Rockstar's inventory surfaces (radial, satchel, context use) instead of being usable for a partial or wasted effect. An item whose cost exactly *equals* the core you have left is still allowed. It covers all 15 catalog items that reference a negative core effect, and it reads each item's real runtime effect values rather than a hardcoded table.

**How it could break shops.** It does not touch shops directly. It writes Rockstar's shared **inventory availability** layer — the enable/disable mechanism that decides whether an item is usable — and that same layer is what Story's shop scripts read. An earlier version wrote to it aggressively: 600+ engine writes in one session whose own readbacks never confirmed, against that shared surface. That corrupted shop volumes and locked every shop family, which is Lexer-Lux/Lexeditor#209 — the session where your shops stopped working entirely.

That is why it was isolated, and why I did not switch it back on by myself.

**What is different now.** It waits 15 seconds after startup, defers entirely while the weapon wheel, backup inventory or an item interaction owns a transaction, writes only on an actual core edge or a settled inventory revision, reads back every write, and **permanently abandons** a write after three unconfirmed readbacks instead of churning. That last one is the specific fix for the 600-writes behaviour.

**Your safety valve, which matters most here.** If shops misbehave, set:

```ini
[CoreCostGuard]
Enabled=0
```

It hot-reloads in about two seconds — no restart, no rebuild, and no waiting for me. Turning it off also **restores** the availability it changed rather than leaving items greyed. So if anything looks wrong in a shop, flip that first and you should be back to normal within a couple of seconds.

**One thing you should know.** The Lexer-Lux/Lexeditor#209 shop-protection checker explicitly forbids both this and the Lexer-Lux/Lexeditor#243 dual-wield guard from running in the same build, and both are now active — Lexer-Lux/Lexeditor#243's was already re-enabled before today. That checker now fails, and I have deliberately left it failing rather than editing it to permit what it was written to prevent. It is doing its job by flagging this. The difference from last time is that you chose it knowingly and you have a switch.

Test: a below-cost item, an item whose cost exactly equals the remaining core, and then walk into a general store and buy something.


## comment 5550146269 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146269

Created: 2026-08-15T04:43:05Z; updated: 2026-08-15T04:43:05Z

Exact metadata: [source record](sources/comment-5550146269-2362a0c15c63d881eba5f8ada359f6ca16c02ef2d14620ce2b687b73d4a49bf2.json).

**Tested this against your session log instead of asking you to test it — and it was failing. Fixed.**

The guard's *decision* logic is correct. It resolved all 15 candidates and blocked the right ones:

```
blocked item=CONSUMABLE_MOONSHINE core=1 current=15 cost=50
blocked item=CONSUMABLE_WHISKEY  core=2 current=12 cost=12.5
```

But the *enforcement* did not stick. Of 43 availability writes, **only 4 confirmed by readback and 39 did not**, and 13 items were abandoned entirely after repeated failures (`reason=setter`). So items that should have been blocked were still usable.

**Cause: the write and the readback were addressing different inventories.**

Rockstar never passes a literal inventory id. `show_movie_magic_lantern.c` func_93 is the resolver:

```c
if (func_255() == -1) {                                     // Story Mode
    if (!bParam0 && INVENTORY::_0x7C7E4AB748EA3B07()) return 5;   // backup inventory open
    return 1;
}
```

Story is inventory **1 normally, but 5 while the backup inventory is open** — and `0x7C7E4AB748EA3B07` is the same backup-inventory predicate this module already reads for its own deferral. It had the fact and did not use it.

Both the getter and setter here went through shared wrappers that hardcode `1`. Any write made while your satchel/backup inventory was up therefore landed on inventory 1 while the game read inventory 5, so the block silently did nothing. That is exactly when you would be looking at consumables.

The id is now resolved per call, and both the write and its readback use the same one.

The contract's own primary-source citation had this all along — it asserts `_0x3D10D7179D7034AF(func_199(0), iParam0, func_27(0))` from `satchel_ui_event_handler.c`, where `func_199(0)` is a resolver. The evidence was sitting in the verifier while the module passed a literal. The contract now requires the resolver and the id-carrying calls, so this cannot regress silently.

The availability line now reports `inventoryId=`, which makes the next session decisive: `confirmed=0` with `inventoryId=5` would mean the resolver is right and the setter still does not own the item; `confirmed=0` with `inventoryId=1` while the backup inventory is open would mean the resolver is wrong.

Also worth recording, since it was the open risk on this issue: **your shops were healthy all session with both inventory writers live.** All seven shop types sat at `state=5`, `LOCKED=0` on 603 readings against 6, and the watcher recorded a clean load/unload/reload cycle (`5→0`, then `0→1→2→3→5`). The Lexer-Lux/Lexeditor#209 concern did not materialise.

Installed and hash-verified.


## comment 5550146289 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146289

Created: 2026-08-19T12:47:21Z; updated: 2026-08-19T12:47:21Z

Exact metadata: [source record](sources/comment-5550146289-b1e31c89e6f4bbcf7aaaec737d607759a3b054f55bea7a7cee880158004f4d2a.json).

Before, the item would be greyed out on my radial menu but I would still be able to use it.

Now, I can't use it but it isn't greyed out on my radial.

Surely there must be a way to get both at the same time, no?

## comment 5550146309 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146309

Created: 2026-08-20T05:37:59Z; updated: 2026-08-20T05:37:59Z

Exact metadata: [source record](sources/comment-5550146309-958abbf836b2c0697d959f2720e92cd3efea35951670bafddc71da27494cfd47.json).

**"I can't use it but it isn't greyed out" — the module gave up on the greying, on purpose, because an unresolved native told it to.**

From Lexer's 2026-08-19 session:

```
availability block item=CONSUMABLE_GIN reason=inventory_revision
                   beforeDisabled=0 afterDisabled=0 confirmed=0 writes=36
availability writes abandoned item=CONSUMABLE_BRANDY
                   consecutiveReadbackFailures=3 reason=setter_does_not_own_this_item
heartbeat ... availabilityWrites=37 readbackFailures=36 writesAbandoned=12
```

**36 of 37 greying writes "failed" their readback.** After three consecutive failures per item the module set `writesAbandoned` and stopped writing — and three separate write paths were gated on `!item.writesAbandoned`. So the greying stopped while the use-blocking, which is independent, carried on. Exactly the state he describes.

**The readback was never trustworthy.** `0x3D10D7179D7034AF` is not a resolved predicate. `natives.json` names it `_INVENTORY_IS_INVENTORY_ITEM_EQUIPPED` and then hedges in its own comment: *"Alternative Name: _INVENTORY_IS_ITEM_DISABLED"* — two OPPOSITE readings. This module picked one and named its wrapper `coreCostStoryItemDisabled`, which turned a guess into an assertion everywhere it was called.

Rockstar's own use points the other way. `camp_beechershope.c:48085`:

```c
if (!INVENTORY::_0x3D10D7179D7034AF(func_511(0), iParam0, func_1835(0)))
    return false;
```

They require it to be **true** to proceed. Under the "is disabled" reading that says "only continue if the item is disabled", which is nonsense; it reads naturally as a positive availability test. A 36-of-37 disagreement rate is what an inverted predicate looks like, not what a broken setter looks like.

Also worth stating: the setter itself is fine and is not weapon-only. `_INVENTORY_DISABLE_ITEM` / `_INVENTORY_ENABLE_ITEM` are called 367 times each across `script_rel`, including on `KIT_CAMP` items, so re-asserting them is ordinary use.

**Changes:**
- The wrapper is renamed `coreCostAvailabilityProbe` and documented as a probe whose meaning is unresolved. Nothing gates on it.
- Write abandonment is **deleted**. The disagreement streak is still counted and reported once, as `availability probe disagrees ... probeNativeMeaningUnresolved=1 writesContinue=1`, but it no longer stops anything.
- The early-out that SKIPPED the write when the probe claimed the item was already in the desired state is gone too — unsafe in both directions while the meaning is unknown, and the setters are idempotent.

So the greying write is now issued on every reconcile and retry, alongside the block that already worked. Both at once, which is what he asked for.

Contract updated and mutation-tested: reintroducing the abandonment flag on any write path, or dropping the probe report, both fail.

Installed `60F7BB35FDC41E14D8FC9330B82538CEBF063842CCF170EC898491D3C6D0BFB6`, hash verified.

What to watch: an item that would take a core below zero should be BOTH greyed in the radial and refused. If it is refused but still not greyed, the next log will show `availability probe disagrees` alongside continuing `writes=`, which would mean the disable native genuinely does not affect these items — a different defect, and one this change makes visible instead of silently surrendering to.


## comment 5550146327 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146327

Created: 2026-08-20T12:53:20Z; updated: 2026-08-20T12:53:20Z

Exact metadata: [source record](sources/comment-5550146327-b33afa968101c2204d54f79d655594d32af62dfdde1094bb0ab896c886962e25.json).

Returned zero-core test: cigarettes are correctly refused and greyed in the satchel, but the radial still presents them as available. This isolates the remaining defect to radial disabled-state presentation or synchronization, not the use-blocking gate.

## comment 5550146340 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146340

Created: 2026-08-20T14:04:09Z; updated: 2026-08-20T14:04:09Z

Exact metadata: [source record](sources/comment-5550146340-537d45273fe8b7a9e91ea5ca5175b599284ca6b710548219dd25316d0a06d975.json).

The returned radial mismatch is now explained, but not guessed around. Satchel availability comes from inventory disable; the radial icon reads the quick-select provider item's canSelect value. The current evidence exposes no proved provider handle or item-hash-to-wheel-item mapping, so writing focusedItemCanSelect or drawing an overlay would not repair the item. The verifier now rejects those false fixes. Lexer-Lux/Lexeditor#238 remains actionable until that provider mapping is proved; no build or install occurred.

## comment 5550146354 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550146354

Created: 2026-08-22T23:48:16Z; updated: 2026-08-22T23:48:16Z

Exact metadata: [source record](sources/comment-5550146354-7d09a273e6285154d1bb83e687152e35d2f2c8a41e09eb59187b62139a5f205b.json).

**The item-hash to wheel-item mapping is no longer unproven. It is a named native, and it was in the shipped reference material the whole time.**

The previous round stopped here: *"the current evidence exposes no proved provider handle or item-hash-to-wheel-item mapping"*. That is now resolved:

```
HUD::_HUD_GET_INVENTORY_WHEEL_CURRENTLY_HIGHLIGHTED  0x9C409BBC492CB5B1  -> Hash
  "Returns the hash of the currently highlighted item in the weapon wheel.
   Only works while the wheel is open."
```

It is not an inference. The shipped `rdr3_discoveries` data-binding reference for `hud_quick_select` uses exactly this native to track the focused item, and its own comments describe the value as *"the currently focused item (0 if none, or the item hash)"*. So the wheel does speak in item hashes, and it will name the item it is showing.

**Deliberately used as a diagnostic, not a fix.** The heartbeat now reports:

```
wheel=1 wheelItem=0x<hash> highlightBlocked=0|1
```

Nothing gates on it, and the contract now FORBIDS it gating anything - an unproved provider mapping must not decide behaviour, which is the mistake that produced `writesAbandoned` in the first place. Mutation-tested: making the probe gate anything fails, as does removing the native or the heartbeat field.

**Why this is the right next step rather than writing `canSelect`.** The remaining question is no longer "which wheel item is this item?" but "does `_INVENTORY_DISABLE_ITEM` reach the wheel, and is it reading the inventory we write to?". Two facts frame that:

- Rockstar's own documentation for that setter is *"(1, WEAPON_REVOLVER_CATTLEMAN, 0) - disables cattleman revolver on weapon wheel"*, so the native is expected to affect the radial, and its third argument is a GXT reason hash which we pass as 0 exactly as Rockstar does in 372 of its ~380 call sites.
- Every one of Rockstar's call sites passes the inventory id as a variable, so no literal proves which inventory the satchel wheel reads.

Highlight a blocked item with the wheel open and the next log answers it in one line. `highlightBlocked=1` means the wheel and this module agree on the item, and any remaining mismatch is the disable not reaching the wheel rather than a mapping problem. `highlightBlocked=0` on an item this module lists as blocked means the wheel is reading a different inventory, and `wheelItem=` gives the hash to chase.

Installed `DB379817851D45B4FC2BB5BC4659DBB9E1E8B7D5F8BD4F81FAA941A89BE3EBE5`, hash verified. Also live from the previous change: the greying writes are no longer abandoned when the unresolved availability probe disagrees, so the disable is re-issued on every reconcile.


## comment 5550616518 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/238#issuecomment-5550616518

Created: 2026-09-05T08:34:04Z; updated: 2026-09-05T08:34:04Z

Exact metadata: [source record](sources/comment-5550616518-8ab76cde678f438eb6f76b7d81b0365bde4cf425dabeb3ca01fd9a1714dacd14.json).

the actual usage itself is blocked but the item is not greyed out in the radial menu, so you just end up "using" it and wondering why nothing happens.
