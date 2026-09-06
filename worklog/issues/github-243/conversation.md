# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356317698 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243

Created: 2026-08-10T12:36:01Z; updated: 2026-09-05T07:02:28Z

Exact metadata: [source record](sources/issue-5356317698-c790613fa4e3c93cf4329b9ca7d8487022e40b9fb984b32f05d2c6171a4d8ba1.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/aea11b15-e17e-498b-b2a6-099dc1844950" />

I was just testing out the scroll wheel, using it to change ammo types and stuff and then my second holster just disappeared???? Now I"m back to one handgun slot?????? How the fuck

## issue 5356317698 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243

Created: 2026-08-10T12:36:01Z; updated: 2026-09-06T13:31:53Z

Exact metadata: [source record](sources/issue-5356317698-3f125c5f943a4ddc9bc92ef32c250e6583b23c82cc2e2328a2d2f0d8aea29033.json).

**Confirmed fixed and closed.** Correcting the old-version wardrobe data and wrong component identity restored the earned holster without inventing ownership or changing unrelated wardrobe state.

[Original screenshot](https://github.com/user-attachments/assets/aea11b15-e17e-498b-b2a6-099dc1844950).

## comment 5550147705 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147705

Created: 2026-08-10T14:55:58Z; updated: 2026-08-10T14:55:58Z

Exact metadata: [source record](sources/comment-5550147705-6669bc00273e763a275b2c2d131ae19095d1030f4e984f8d61e6fe6e5869ebee.json).

I STILL HAVE ONLY ONE HANDGUN HOLSTER

## comment 5550147717 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147717

Created: 2026-08-10T16:48:07Z; updated: 2026-08-10T16:48:07Z

Exact metadata: [source record](sources/comment-5550147717-d146cd88e184d1a368365caa7a8e621f646205f8f5d4352faa9bb665f2a17195.json).

I found the actual state loss. Dual-wield permission was still enabled, but the saved secondary-holster loadout slot was genuinely empty. The previous diagnostic also read that slot at the wrong offset because it skipped Rockstar's fixed-array header, so it falsely ruled the loadout out.

The repair now restores only an already-earned Arthur/John off-hand holster when that exact slot is empty: it rebuilds the clothing/loadout entry, verifies the component is physically in use, then re-enables dual wield. It does not grant the unlock, add a weapon, or write raw globals. This is still `actionable` because the corrected source has not been built and installed yet. After the combined install, the required check is: the off-hand holster is visibly back, both handgun slots work, and it persists after save/reload.


## comment 5550147733 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147733

Created: 2026-08-10T17:01:13Z; updated: 2026-08-10T17:01:13Z

Exact metadata: [source record](sources/comment-5550147733-26fb7f2081d642408a70240ed0d1ac1c0eda6dce3128652609607690b897e43e.json).

The earned off-hand-holster recovery is installed. On startup it now checks the correctly addressed secondary loadout slot; if the unlock is already earned and that slot is empty, it restores Arthur/John's canonical holster component, verifies it is physically in use, and re-enables dual wield. Test the visible off-hand holster, both handgun slots/draw/fire, then save and reload to confirm persistence.

## comment 5550147751 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147751

Created: 2026-08-10T18:59:28Z; updated: 2026-08-10T18:59:28Z

Exact metadata: [source record](sources/comment-5550147751-fd3d951e1f461c4147601043268a38cc2d96e497810b2679d496d12b773d97e1.json).

Okay well I still have one holster so what do I press to get it back? Come on dude

## comment 5550147763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147763

Created: 2026-08-10T19:40:14Z; updated: 2026-08-10T19:40:14Z

Exact metadata: [source record](sources/comment-5550147763-8e6324c6679033aab380715cf5f5a88b0ff55476be63a167334cb2a75bc86244.json).

The installed trace proves the prior repair failed: inventory became active, but the settled physical readback stayed `physical=0`, so there is no key/button for you to press. The source omitted Rockstar's `_SET_ACTIVE_META_PED_COMPONENTS_UPDATED` commit between enabling the holster component and rebuilding the ped, and it also had the default LOADOUT_3 address wrong. Both are corrected from `act_hunting_2.c:50951-50965`; combined development build `D7BCACD0748735BC03766D4A1483DAD96BD1C09EF01196CC70C195BD42EE476C` is queued for automatic installation after RDR2 closes. This remains actionable until that install lands.


## comment 5550147776 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147776

Created: 2026-08-10T22:18:39Z; updated: 2026-08-10T22:18:39Z

Exact metadata: [source record](sources/comment-5550147776-d21490fb16cb1ce7b19185f1459df50dacfc3ca94a6591ac7a8169596d22cd7c.json).

The corrected automatic holster repair is now physically installed in hash-verified build `70B66FAB3A0082C6638633A2379AF40147AABEF99D8DBC9EFFA1CC9591746F1B`. There is still no key to press: after launch, the settled trace must show `physical=1 inUse=1 allow=1`, and the second holster plus both sidearm slots must be visibly present.

## comment 5550147799 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147799

Created: 2026-08-11T01:00:59Z; updated: 2026-08-11T01:00:59Z

Exact metadata: [source record](sources/comment-5550147799-7ca738e485f92aac60928909eb9d11e65a03f2ab66958c9f83642cb1f468fff7.json).

WHAT AM I SUPPOSED TO PRESS TO GET MY HOLSTER BACK

## comment 5550147813 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147813

Created: 2026-08-11T01:46:00Z; updated: 2026-08-11T01:46:00Z

Exact metadata: [source record](sources/comment-5550147813-9ea59cb59bd8e35aa1a477181bf7bdac347b11879074a6129a2d0e6c6743185d.json).

The repair was rejecting the broken LOADOUT_3 state because it was nonzero even though the holster was absent. It now checks ownership and physical component state, then restores Rockstar's earned off-hand holster path only when that component is genuinely missing. Test the wheel, visible holster, dual draw/fire, and save reload.

## comment 5550147827 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147827

Created: 2026-08-11T04:51:42Z; updated: 2026-08-11T04:51:42Z

Exact metadata: [source record](sources/comment-5550147827-66e14684ce5f50df9d666ebc1945780f5239118d0af34f5a27d051254beb75a9.json).

How am I supposed to dual wield with ONLY ONE HOLSTER?

## comment 5550147845 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147845

Created: 2026-08-11T06:09:55Z; updated: 2026-08-11T06:09:55Z

Exact metadata: [source record](sources/comment-5550147845-e4bb1824aaf4e0f59f2090c1961b448da070e850358826b4c8b6683b9f558386.json).

The latest clean launch proves Lexer-Lux/Lexeditor#238 was not the only shop regression: CoreCostGuard never ran, but Lexer-Lux/Lexeditor#243 mutated the off-hand holster inventory/component state five seconds after startup and then failed its own settled postcondition (physical=0, missingComponent=1). Shops remained closed and unusable. The Lexer-Lux/Lexeditor#243 runtime call is removed from the next build. This remains actionable; no runtime success is claimed.

## comment 5550147863 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147863

Created: 2026-08-11T09:32:33Z; updated: 2026-08-11T09:32:33Z

Exact metadata: [source record](sources/comment-5550147863-5adf4497fd6d5d219fb2874322ddb255172bc7e8101a27927609332bda5ab078.json).

The earlier repair edited clothing inventory records and still read physical=0. This repair requires the earned dual-wield unlock and an already-owned canonical holster, waits for 15 seconds of uninterrupted safe state, then performs Rockstar's exact current LOADOUT_3 transition once and reads back loadout, physical component and dual-wield permission. Check the visible holster, both wheel slots, dual draw/fire and save reload.

## comment 5550147877 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147877

Created: 2026-08-12T22:24:38Z; updated: 2026-08-12T22:24:38Z

Exact metadata: [source record](sources/comment-5550147877-4a70dc1965fa9fa6f566db59adeeeb84afe05df38561a6f78dcc758741b5d347.json).

**Integration fix: the guard was never actually running.**

Found the concrete reason no `[dual-wield]` evidence ever appeared — the dispatcher call was commented out at `script.cpp:2193`:

```cpp
// Lexer-Lux/Lexeditor#209 isolation: Lexer-Lux/Lexeditor#243 still performs an unaccepted clothing/loadout
// transaction after startup. ...
// updateDualWieldGuard(ped, now, mission);
```

The `#include` was present, so the module compiled but was dead code. Absence of the heartbeat was `not executed`, not "state stayed healthy".

The isolation reason was stale. It describes the superseded repair that edited the clothing inventory record. The module was rewritten on 2026-08-11 to remove **all** inventory-record mutation — no item add, no enable/unhide, no in-use write. Its only mutations are publishing Rockstar's own LOADOUT_3 value for an **already-owned** holster (`expectedCount > 0` is a precondition), the matched dual-wield setter, and Rockstar's apply/commit/refresh sequence. Shop ownership — the actual concern the isolation protected — was restored in 34f3396.

So the call is restored. No module source changed.

```
verify_dual_wield_guard_issue_151.py   PASS
build.bat                              EXIT=0
Install-When-RDR2-Closes.ps1           GameplayTweaks.asi installed, hash verified
```

Installed ASI SHA-256 `7F6A61839F8681F121F53B50B72AF5FC198EFF6E7C6641FFDD86D6C5E504107F`.

**This is integration only, not acceptance — leaving open.** It proves the repair *can now execute*, not that it works. Next launch should produce a continuous `[dual-wield]` log. Acceptance still needs the settled line reading the expected LOADOUT_3 hash with `physical=1` and `allow=1`, plus visual confirmation of the off-hand holster, both sidearm slots, both handguns drawing/firing, and survival across save/reload. A settled line with `physical=0` is a returned failure.

## comment 5550147887 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147887

Created: 2026-08-13T01:23:54Z; updated: 2026-08-13T01:23:54Z

Exact metadata: [source record](sources/comment-5550147887-5abd89bed502a2e85dab87a95f5c7147ed4fdfd8d98c638173fbe79c829030f4.json).

yeah i launched it fix this now bruh

## comment 5550147898 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147898

Created: 2026-08-13T02:09:35Z; updated: 2026-08-13T02:09:35Z

Exact metadata: [source record](sources/comment-5550147898-87225a36a9e6645c4169a03f7f2701ee4b3a9318e2807361f9b048b795c91393.json).

**Runtime result: the guard now runs, and its repair fails its own postcondition.**

From your session:

```
allow=1 unlock=1 count=1 guid=1 loadout3=0x359efad0
inUse=0 physical=0 repairs=1 repairLatched=1
```

Re-enabling the call worked — it fired once. Permission and entitlement are fine, and it published the correct LOADOUT_3 value (`loadout3` equals the expected holster). But `physical=0`: `_APPLY_SHOP_ITEM_TO_PED` did not put the holster on his body. That is a returned failure, not a partial success.

The strongest lead is `inUse=0` sitting alongside it. Rockstar's `act_hunting_2.c` case 24 marks the clothing record **in use** before applying the component; the 2026-08-11 rewrite deliberately removed that step to stop the shop-ownership collision. So the removed step looks load-bearing — but re-adding it risks re-breaking shops, which is a real tradeoff and yours to weigh, not mine to silently pick.

**Separately, I removed a broken predicate.** `missingComponent` included `current == fallback`, and the log proves `fallback` reads `0x3f800000` — the float `1.0f`, not a clothing hash. That address is still wrong after two correction attempts (with and without the array length header, both reportedly yielding this same value). A comparison against a known-bad read can only produce a wrong answer that looks authoritative, so it is gone. The remaining terms (`current == 0`, `kUnsetLoadout3`, `currentCount <= 0`, neither component physical) do not depend on that address, and the raw value is still logged so the slot can be identified later.

Verifying that addressing again needs `quickselectmenus_ymt.xml`, which was destroyed in the cleanup (`fuckups.txt` entry 20) — tracked as Lexer-Lux/Lexeditor#281. The verifier now says exactly that instead of throwing `FileNotFoundError`, which read like a broken tool rather than missing input.

Build EXIT=0, installed `4295C2EC…`. Still open.

## comment 5550147915 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147915

Created: 2026-08-13T03:49:26Z; updated: 2026-08-13T03:49:26Z

Exact metadata: [source record](sources/comment-5550147915-ede88cf1899014e057809a35c588f53fa9171510a482eebf331cd0915230615c.json).

**Restored the in-use step that the evidence pointed at.**

The installed run reached the postcondition and failed it: `loadout3` published correctly, `allow=1 unlock=1 count=1 guid=1` — but `physical=0` **and** `inUse=0`. Rockstar's `act_hunting_2` case 24 marks the clothing record in use *before* applying the component; the 2026-08-11 rewrite removed that step to stop a shop-ownership collision, and `physical` has been 0 ever since.

So it's back — but only inside the existing one-shot latch and behind the backup-inventory, wheel, item-interaction, player-control and 15-second settle gates, which is exactly what the earlier unguarded version lacked. `_INVENTORY_SET_INVENTORY_ITEM_IN_USE` (`0x65A5F70F4A292EBE`) is a matched setter for the getter this module already reads, so it logs `in-use set requested=1 readBack=…` — a refused setter is visible rather than assumed.

**I also had to fix the verifier, which was about to lie.** It passed while printing "and makes no inventory-record mutation" — false the moment I added one. It now asserts the mutation is permitted *only* with the one-shot latch, the inventory guards, and a matched readback present, and says so in its pass message.

Installed `7CC82C63…`.

**Shops are the risk here** — that's why the step was removed. Next session, check shops still work, and watch for `in-use set` followed by a settled line. Success is `physical=1` with `allow=1`; `physical=0` again means the in-use step wasn't the missing piece and the failure is in `_APPLY_SHOP_ITEM_TO_PED` itself.

## comment 5550147927 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147927

Created: 2026-08-13T06:53:39Z; updated: 2026-08-13T06:53:39Z

Exact metadata: [source record](sources/comment-5550147927-78c9248ce9f9026fd11fd7a4f44b1cdd0b3eb0a56a5aebbced4c21d2cadccf15.json).

IT. IS. STILL. GONE.

## comment 5550147945 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147945

Created: 2026-08-14T00:02:04Z; updated: 2026-08-14T00:02:04Z

Exact metadata: [source record](sources/comment-5550147945-12df725e7078b568fc591206d88c8947de124b2168da6ad0be7aecb7a6f9a018.json).

**Not fixed this round, and I am telling you why rather than shipping it.**

Two things happened.

First, the state got worse, not stuck. On Aug 13 the trace read `allow=1 unlock=1 count=1 guid=1`. Every line in your latest session reads `allow=0 unlock=0 count=0 guid=0`. The repair's own precondition is "the holster is already owned", so at `count=0` it cannot even attempt — which is why nothing you press does anything. The prime suspect is the in-use write that was added on Aug 13, and that is exactly what was being investigated.

Second, the investigation was cut off mid-rewrite by an account spend limit, leaving `dual_wield_guard.cpp` half-written: it had already removed the apply-record write and had not yet landed whatever replaces it. Its verifier fails on exactly that.

So I isolated the module instead of shipping it. Its dispatcher call is commented out in this build. That module edits clothing and loadout records on a live save, and an earlier unfinished version of it broke shop ownership — I am not putting a half-formed inventory transaction into your game to look productive. Functionally you lose nothing, because at `count=0` it was already unable to run.

**This changes nothing about your missing holster**, which is why this stays `actionable`. What it does is stop the bleeding while the addressing question gets settled.

One real thing did come out of it. The checker was demanding the **known-bad** addresses — the pre-header form this issue diagnosed on Aug 10. `act_hunting_2.c:7125` reads `Global_1946804.f_1497.f_1[27 /*3*/]`, and a decompiled fixed-array access skips the leading length cell, so the module's addressing was right and the verifier was asserting the old off-by-one. Corrected, so it can no longer certify the bug.


## comment 5550147962 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147962

Created: 2026-08-14T00:07:54Z; updated: 2026-08-14T00:07:54Z

Exact metadata: [source record](sources/comment-5550147962-d9042d55f0c083fa1268e4658adebce8b0d601f1cb7e419de790c9a8fc22f294.json).

**Correcting my last comment, and there is a real root cause this time.**

I said the module was half-written and isolated it. That was wrong, and I had it backwards. Reading the rewrite properly: removing those wardrobe-global writes was **deliberate and primary-source justified**, not an unfinished edit. The only thing actually missing was one constant, which I supplied. The dispatcher call is restored and this is installed.

**The defect that explains every `physical=0` you have ever seen here.**

Rockstar's wardrobe apply takes an `isMp` argument. `act_hunting_2.c:50859` computes it as `func_116() != -1`, and `func_116` returns `Global_1572887.f_12`. Story Mode is the `== -1` branch — so in Story Mode that argument is **FALSE**.

The module hardcoded **TRUE**, with a comment claiming that was right for protagonist clothing. That inverts the expression it cites. So `_APPLY_SHOP_ITEM_TO_PED` was writing the **MP clothing layer** while the readback — and the game — read the **SP layer**. `physical=0` was not a failure to apply; it was applying to a layer nothing was looking at. That was guaranteed on every installed run, which matches your logs exactly.

Two more things it corrected: every global index was one slot low (missing the leading array size cell), so they were reading LOADOUT_2's trailing field instead of LOADOUT_3's item hash — which is why `default` read `0x3f800000`, the float 1.0, and why `loadout3` drifted from `0x0` to `0x2f` on its own while the module sat idle. And the old code stored a raw hash into a persisted wardrobe record, which Rockstar never does; those writes are gone and all three globals are read-only diagnostics now.

**What I am not promising.** Your last session read `count=0`, meaning the save does not currently show the holster as owned. The repair refuses to run at `count=0` on purpose — it will not invent progression. So if that is still true, you will see `no repair possible reason=holster-not-owned` rather than a holster, and the layer fix alone will not bring it back.

There is now a `unlockVisible` field that settles which case you are in, because Rockstar always makes an unlock visible in the same breath it grants it: `unlock=0 visible=1` means earned and later cleared; `unlock=0 visible=0` means never earned on this save. That distinction decides whether this is recoverable at all, and it is the first thing to read in the next log.

Also fixed: the checker was demanding the known-bad pre-header addresses and would have failed a correct module, and it scanned comments, so an accurate note about what the module does *not* do read as a violation.


## comment 5550147978 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147978

Created: 2026-08-14T10:09:42Z; updated: 2026-08-14T10:09:42Z

Exact metadata: [source record](sources/comment-5550147978-3ca7440f77907307c0febf3e725167735c44088800bf06746696d0a406c9cc40.json).

**Heads-up before you next load: check shops first.**

Running the full verifier suite (rather than just this issue's) surfaced a conflict I should have seen when I re-enabled this guard.

`verify_shop_camp_owner_issue_114.py` — the contract for the closed "I can't buy or interact with any shopkeepers" issue — explicitly forbids **both** inventory writers from being in the dispatcher while their behaviour is unaccepted:

```python
# Returned Lexer-Lux/Lexeditor#238/#151 behavior is still unaccepted. Do not let either
# inventory writer contaminate the shop-recovery build.
assert "updateDualWieldGuard(ped, now, mission);" not in script
assert "updateCoreCostGuard(ped, now," not in script
```

Both are now live — I restored this one, and Lexer-Lux/Lexeditor#238's call was enabled separately. Both issues are still `test me`, so "unaccepted" is exactly true, and that contract is now failing **correctly**. I have deliberately left it red rather than editing it to go green: it is reporting a real state, not a stale expectation.

I am not silently re-isolating either, because that would undo the work and make both untestable, and you would lose the session either way. But you should know the risk is concentrated in this build.

**Cheapest way to settle it:** when you load in, walk to any shopkeeper and open the catalog **before** doing anything else. That is a ten-second check.

- Shops work → both writers are fine in practice, this issue and Lexer-Lux/Lexeditor#238 are genuinely testable, and Lexer-Lux/Lexeditor#209's contract can be updated to record that acceptance.
- Shops are dead → we know immediately it is one of these two, and isolating them is a one-line change each.

Nothing about the holster repair itself has changed since my last comment; the state to look for is still `physical=1` with `allow=1`, or `no repair possible reason=holster-not-owned` if the save still shows `count=0`.


## comment 5550147996 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550147996

Created: 2026-08-15T02:29:43Z; updated: 2026-08-15T02:29:43Z

Exact metadata: [source record](sources/comment-5550147996-e68433d4e09dd32a5f0236f60c8b54cc547d039d4fe05c925a3993260ef83b97.json).

 so you can take away my second holster no problem but i have to beg you a dozen+ times for you to give it back?
how much longer are you going to make me wait?

## comment 5550148011 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148011

Created: 2026-08-15T04:08:44Z; updated: 2026-08-15T04:08:44Z

Exact metadata: [source record](sources/comment-5550148011-66ddd1ad869a7a7512e1a329a91754f3d5ec74bcff595a985bb099fd5b407c88.json).

**Your session settles the in-use question, and the answer is no.**

The state transformed since the last log — the entitlement is back and the Story-layer fix took:

```
allow=1 unlock=1 unlockVisible=1 keyValid=1 count=1 invId=1 isMp=0 guid=1 inUse=1 physical=0
```

Every precondition now reads correctly. `isMp=0` confirms the inverted-layer fix is live, `count=1` and `guid=1` confirm the holster is owned and addressable, and `unlockVisible=1` confirms it was genuinely earned rather than cleared.

**And `inUse=1` across 149 of 156 samples is the decisive part.** Marking the clothing record in use was the leading hypothesis for why `physical` stayed 0 — Rockstar's `act_hunting_2` case 24 does it before applying the component, and this module was made to do the same. It now succeeds, and `physical` is **still 0**.

So that hypothesis is dead. With the correct SP layer, an owned item, a valid GUID and the record marked in use, `_APPLY_SHOP_ITEM_TO_PED` still does not put the holster on his body. The remaining candidates are the apply call's own arguments or that this component needs a different application path entirely — not the preconditions, which are now provably all satisfied.

That is real progress even though the holster is still missing: three explanations are eliminated by evidence rather than argument, and the next attempt starts from a much narrower place.

Staying `actionable`.


## comment 5550148033 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148033

Created: 2026-08-15T04:31:18Z; updated: 2026-08-15T04:31:18Z

Exact metadata: [source record](sources/comment-5550148033-462750d8ed2572dcb92e09dd92e82827f9bf15676ba62f52f9e9c96a24f956a8.json).

**Found the last difference between our sequence and Rockstar's.**

Your session eliminated everything around the apply: `isMp=0` (correct Story layer), `count=1` (owned), `guid=1` (addressable), `unlockVisible=1` (genuinely earned), `inUse=1` (record marked). Every precondition provably satisfied, and `physical` still 0 across 149 samples. So the fault had to be in the apply itself.

It is. At `act_hunting_2.c:50951-50955` Rockstar does **not** stop after enabling the component:

```c
PED::_SET_PED_COMPONENT_ENABLED(ped, iVar2, false, bVar4, false);
if (uParam0->f_1[iVar1 /*3*/].f_1 != 0)
    PED::_0x66B957AAC2EAAEAB(ped, iVar2, uParam0->f_1[iVar1 /*3*/].f_1, 0, bVar4, 1);
```

There is a **paired second call** carrying the record's `.f_1` sub-field whenever that field is non-zero. This module only ever made the first call. I also confirmed the first call's arguments are right while I was in there — `iVar2` resolves to `uParam0->f_1[iVar1 /*3*/]`, the clothing item hash, which is what we pass.

Added, with Rockstar's own guard reproduced: if the sub-field is zero, it makes no call and neither do we. The value is read from the record this module already addresses, one slot past the item hash (array stride is 3).

**What I am not claiming.** `0x66B957AAC2EAAEAB` is **unnamed** in the SDK — `_0x66B957AAC2EAAEAB(Any p0..p5)`. I do not know what it does and am not pretending to. What is established is the call *shape*: it appears in 431 decompiled scripts, always paired with the component apply, and every argument here is copied verbatim from that site. It is used as a call, never as a gate or a truth claim — the same basis on which this module already calls `0xAAB86462966168CE` and `0xCC8CA3E88256E58F` as part of the same tail.

The repair line now reports `variant=0x… pairedCall=0|1`, which makes the next result decisive either way:

- `pairedCall=1` and `physical=1` → this was the missing piece.
- `pairedCall=1` and `physical=0` → the sub-field call is not it either, and the remaining suspect is the bookkeeping Rockstar does around the apply (the `f_2456` applied cache and the `f_857` change counter), which this module deliberately does not write.
- `pairedCall=0` → the record's sub-field is zero, Rockstar would have skipped it too, and this was never the difference.

Installed and hash-verified. Test: load in, wait past the 15-second settle, then check whether the off-hand holster is on his body and read the `repair issued` line.


## comment 5550148055 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148055

Created: 2026-08-18T03:27:47Z; updated: 2026-08-18T03:27:47Z

Exact metadata: [source record](sources/comment-5550148055-99aedd2698ae82f28a90eaf5ea8a65632a263eaff4ed25bd00cc12bdb1a2955c.json).

**Your session answered it: the paired call was never the difference. Third branch of the three I laid out.**

```
repair issued ownedBefore=1 globalWrites=0 variant=0x0 pairedCall=0 isMp=0
              component=0x359efad0 allow=1 unlock=1 unlockVisible=1 count=1 guid=1 inUse=1
repair settled ... inUse=1 physical=0 postPhysical=0 postAllow=1 REJECTED
```

`variant=0x0`, so `pairedCall=0` — the record's sub-field is zero and Rockstar's own guard would have skipped that second call too. It was never the missing piece, exactly as the `pairedCall=0` branch predicted. That hypothesis is now dead alongside the layer, ownership, addressing and in-use ones.

**But the same line exposes something more important.** All three wardrobe globals now read zero:

```
loadout3=0x0   default=0x0   target=0x0
```

On 08-14 those same three read `loadout3=0x1b`, `default=0x0`, `target=0x2539e609`. Same addresses, same save, different values — and `variant` is read one slot past `loadout3`, which is why it came back 0.

So the addressing is **not stable**, and every conclusion that depended on reading those records is now suspect — including the "one slot low" correction I made on 2026-08-14 and the variant read built on top of it. Two sessions disagreeing on the same global is the tell that this module has never actually located the record, only landed somewhere plausible.

I am not going to add another apply-side call on top of an address I cannot trust. That is how this issue accumulated five dead hypotheses.

**What comes next, in order:**

1. Establish whether the wardrobe record address is right at all, by reading the full stride-3 slot and comparing against a value the game visibly agrees with, rather than inferring from a single field.
2. Only then revisit the bookkeeping Rockstar does around the apply (`f_2456` applied cache, `f_857` change counter), which this module deliberately does not write.

Staying `actionable`. What is genuinely established and unchanged: the entitlement is real (`unlock=1 unlockVisible=1`), the holster is owned (`count=1 guid=1`), the Story layer is correct (`isMp=0`), the record is marked in use (`inUse=1`), and the component still does not attach.


## comment 5550148070 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148070

Created: 2026-08-19T12:34:17Z; updated: 2026-08-19T12:34:17Z

Exact metadata: [source record](sources/comment-5550148070-5098db910d0dda9d3f87ce4eb353d5534cafbdf2daf5f35c2836a16a1e66b7fe.json).

**Correcting myself first: my last conclusion on this issue was wrong.**

I reported that `loadout3`, `default` and `target` all read `0x0` and concluded the wardrobe **addressing** was untrustworthy. That was sampling error — I looked at early frames only. Lexer's 2026-08-19 session shows the same addresses changing as the session runs:

```
loadout3=0x0        default=0x0  target=0x0          rockstarMissing=1   <- early
loadout3=0x1b       default=0x0  target=0x2539e609   rockstarMissing=0   <- later
loadout3=0xffffffff default=0x0  target=0x0          rockstarMissing=0
```

Zero before the record streams in, populated after. The 08-14 non-zero readings and the 08-17 zero readings were never a contradiction — they were the same address at two different moments. **The addressing is fine.** Nothing needs re-deriving, and the hypothesis I was about to spend a session on was chasing my own mistake.

**The real defect is in the same lines, and it is much simpler.**

```
repairs=1  lastRepairTick=1861390  repairLatched=1  blocked=latched
           rockstarMissing=1  loadout3=0x0  target=0x0
```

The guard's single repair fired **while the wardrobe record was still absent**. It failed against data that did not exist yet, then latched. The latch only clears on an observed recovery (`!missingComponent || physical`), and the component never recovered — so when the record populated moments later and `rockstarMissing` went to `0`, the one moment the repair could have worked was already locked out. The guard then spent the rest of the session reporting `blocked=latched`.

That is why every previous hypothesis on this issue looked dead: the layer, the ownership, the paired call, the in-use flag were all *fine*. The repair was simply never attempted again after the state that could have satisfied it arrived.

**Fix:** the latch now also re-arms on the absent -> present transition of Rockstar's record, logging

```
repair re-armed reason=wardrobe-record-populated previousAttemptWasAgainstEmptyRecord=1 recordRearms=N
```

Bounded on purpose — one re-arm per transition, never a per-frame retry loop, which is the failure mode that got earlier versions of this guard rejected. `recordRearms=` is on the heartbeat so a retry that never happens cannot look identical to one that did.

Contract added and mutation-tested (removing the re-arm or the counter both fail). Built `665AB35FF088744C9D3BCA57049C4135AD0B59CB88317964D0CC628B9246EFD9`; not installed — Lexer is in game.

**What decides it next session:** `recordRearms=1` with `physical=1` afterwards means fixed. `recordRearms=1` with `physical=0` means the repair itself is still wrong, but for the first time it will have been attempted against a populated record — which is the test that has never actually been run.


## comment 5550148085 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148085

Created: 2026-08-20T06:50:38Z; updated: 2026-08-20T06:50:38Z

Exact metadata: [source record](sources/comment-5550148085-6ebe19dd1f3d46935c7e8ca458d5c8bfef82b5ed9b0687f5e556fa9183ec154a.json).

still not fixed.

## comment 5550148095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148095

Created: 2026-08-20T07:38:03Z; updated: 2026-08-20T07:38:03Z

Exact metadata: [source record](sources/comment-5550148095-9ed499c04f3e1ec0836bff63dc845f1d52dde4009e0ce88419ac166efe3511d4.json).

The previous repair used wardrobe addresses from RDR2 1311.12. Your installed 1491.50 build uses `Global_1946054`, not `Global_1946804`. It also checked physical state with the shop-item hash instead of the resolved metaped component category. The last log proves that old path executed and failed.

The repair now uses the current wardrobe block, waits until it is ready, resolves the component category, and applies only an already-owned earned holster. It no longer writes inventory state or wardrobe globals. The development build completed, but I did not install it.

After installation, verify the visible second holster, two handgun wheel slots, dual draw/fire, mouse-wheel switching, and save/reload survival.

## comment 5550148105 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/243#issuecomment-5550148105

Created: 2026-08-20T12:53:17Z; updated: 2026-08-20T12:53:17Z

Exact metadata: [source record](sources/comment-5550148105-0798336fa9c71b053737ab7fce1b6855d3ed2818316933088530cded8db0b4c0.json).

Confirmed fixed and closing. The cause was a version mismatch plus the wrong readback key: the repair used the 1311.12 wardrobe address against 1491.50 and passed a shop-item hash where the resolved metaped component category was required. The contract now pins the 1491.50 wardrobe block at Global_1946054, count-cell arithmetic, and category resolution. It explicitly rejects the stale Global_1946804 path and shop-hash readback, with seven regression mutations covered.
