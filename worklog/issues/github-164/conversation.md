# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356298676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164

Created: 2026-08-06T02:44:50Z; updated: 2026-09-05T06:58:17Z

Exact metadata: [source record](sources/issue-5356298676-1d7f5c10a06dbfa4b9e90adb044555bdbc847761017c558139a8bcb1f9340a7e.json).

ANCIENT TOMAHAWK RETURNS ON IMPACT — throw it and it comes straight back
     into my inventory the moment it hits the ground or hits somebody. Not after
     a delay, not out of a locker — immediately, on impact. In vanilla you just
     lose it, like the other uniques.
     NOT BUILT. What exists today is a 30-second timer that quietly hands the
     weapon back once its world pickup has despawned. Different mechanic, wrong
     one for this weapon. Separate item from Lexer-Lux/Lexeditor#150 — do not merge them again.


## issue 5356298676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164

Created: 2026-08-06T02:44:50Z; updated: 2026-09-06T12:54:41Z

Exact metadata: [source record](sources/issue-5356298676-32bc044f970ef9e3e48a0a9538de0e5bccda444dfc1d16ef296fc8952a23c54b.json).

The installed repair addresses the stale tracking state that allowed only the first throw to return. Return feedback also needs checking.

- [ ] Fully restart RDR2 and equip the Ancient Tomahawk. Throw it at the ground three times consecutively; each impact should immediately return it, not just the first.
- [ ] Repeat against a wall and a target. Confirm there is one usable copy and note whether the acquisition popup appears. Report which throw fails and attach that session's GameplayTweaks log.

## comment 5550126607 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126607

Created: 2026-08-06T08:09:03Z; updated: 2026-08-06T08:09:03Z

Exact metadata: [source record](sources/comment-5550126607-284b31becd4595ee1c5c9cbaabf1e940bf7cea3f10f5d3c81e05978b7120df5c.json).

The combined release build now includes immediate impact return, separate from Lexer-Lux/Lexeditor#165's locker path. It remains queued until RDR2 exits.

Queued ASI SHA-256: `5E08E021F25A1B0A597B350451514544086EE8898949E98608D0C8BAF05855CC`

## comment 5550126625 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126625

Created: 2026-08-06T08:16:11Z; updated: 2026-08-06T08:16:11Z

Exact metadata: [source record](sources/comment-5550126625-4f19b5a07cce4e2de213a975dcaef90fd1a36d16992a0d7297a4f7c78d19e5a0.json).

Superseding combined build queued; includes immediate Ancient Tomahawk return. It will install when RDR2 exits.

Queued ASI SHA-256: `9124F920A8A97381327D8FF1D2E01A0A3220A793EA9BE475BAF5D7198E9B225B`

## comment 5550126639 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126639

Created: 2026-08-06T12:03:35Z; updated: 2026-08-06T12:03:35Z

Exact metadata: [source record](sources/comment-5550126639-8b954b29073a9989011237a220207a52cc0344e38a9175406ba0c997734bf4e1.json).

i threw it into a tree and now it's no longer in my inventory and still in the tree.
so i'm pretty sure this counts as a failure.

## comment 5550126650 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126650

Created: 2026-08-06T12:44:58Z; updated: 2026-08-06T12:44:58Z

Exact metadata: [source record](sources/comment-5550126650-d6689b3ac7d4f4c6db2691c97c2a58887cbfe875f1eb3a35c7e3a5dc326b389f.json).

no change.

## comment 5550126671 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126671

Created: 2026-08-06T14:42:08Z; updated: 2026-08-06T14:42:08Z

Exact metadata: [source record](sources/comment-5550126671-305dc7ed1e0e8e9231d3d4cf010e2f12c101078f6ab9cc78a8c1f8948d6bed58.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Throw the Ancient Tomahawk and confirm it returns only after impact/ownership loss, not at throw start.

## comment 5550126696 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126696

Created: 2026-08-06T18:15:31Z; updated: 2026-08-06T18:15:31Z

Exact metadata: [source record](sources/comment-5550126696-e1a7fa336d5b1d8cd3cb133bf34130695a94f8d55da6e3db617d3c886075bb95.json).

still just sits there after i throw it.

## comment 5550126708 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126708

Created: 2026-08-06T18:53:31Z; updated: 2026-08-06T18:53:31Z

Exact metadata: [source record](sources/comment-5550126708-588a7f08ad43646cf666de26b2db7bd3f0a29e22a3124ba6e871b7b05d7d4d24.json).

Rewritten. Every impact path in the previous builds was dead code, and one of them rested on a false claim in the worklog.

**The false claim.** The old worklog justified `GET_COORDS_OF_PROJECTILE_TYPE_WITHIN_DISTANCE` (`0xD73C960A681052DF`) by stating `rcm_bh_bandito_shack.c` queries it with the Ancient Tomahawk. It does not. Across `script_rel`, all 1087 call sites pass `WEAPON_THROWN_DYNAMITE` (1086) or `WEAPON_THROWN_MOLOTOV` (1); **zero** pass any tomahawk hash. That file actually uses the coordinate-based `IS_PROJECTILE_TYPE_WITHIN_DISTANCE` for the tomahawk (`rcm_bh_bandito_shack.c:32346`). The query never returned true, so `sawProjectile` stayed false and the `sawProjectile && !projectile` fallback could never fire either.

**The other signal was also wrong.** `GET_PED_LAST_WEAPON_IMPACT_COORD` reports weapon-*fire* impacts and produced no fresh coord for a throwable.

**And the model was wrong.** The old code could only notice a projectile that ceased to exist. A tomahawk embedded in a tree exists forever — exactly your report. Builds 1-2 also armed from `IS_PED_SHOOTING`, which never pulses for this throwable; build 3 added a working ownership-loss edge but still had no live impact signal to reach.

**Now.** `MyOverhaul/pickups.meta` binds `PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT` to model `w_melee_tomahawk02` (01/03/04 are the other variants, so it is unambiguous), and the in-flight projectile carries the same model, so the thrown weapon is directly enumerable. On launch the module baselines every existing `w_melee_tomahawk02` object and pickup except the one attached to you, so the original site spawn can never be misread as your throw. Three independent impact signals per tick: `HAS_ENTITY_COLLIDED_WITH_ANYTHING` on the tracked projectile; moved (>3 m/s) then at rest (<0.5 m/s), which is the tree/ped case; and an unbaselined `w_melee_tomahawk02` pickup appearing. `GIVE_WEAPON` fires on the collision frame, then the world copy is removed — the fresh pickup within 5 m, or the tracked object itself when it is embedded and no pickup spawned.

Decoupled from `g_recoverUniqueWeapons`, so this no longer rides Lexer-Lux/Lexeditor#165 locker path; `world_economy.cpp` still has no tomahawk entry. 30 s with no signal logs `no-signal-abort` and grants nothing — there is no timer, despawn or locker fallback left in the file.

`GameplayTweaks.ancient-tomahawk.log` now carries an `idle` heartbeat every 15 s, so a silent log proves the module is not running rather than leaving it ambiguous, plus a per-tick `scan` line while armed and a `return` line naming which signal fired.

Built, SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, install queued behind the running game. Staying `actionable` until it lands.

## comment 5550126726 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126726

Created: 2026-08-06T18:59:43Z; updated: 2026-08-06T18:59:43Z

Exact metadata: [source record](sources/comment-5550126726-0ef326ae2f6df28877fca4a3de463a2f291692de1fca4b739221859c791bbb4d.json).

Install verified. `GameplayTweaks.asi` in the game root hashes SHA-256 `D7A3A305D74AA519F008336C008451D5CD5348FE3894BBC34E044000F0B0B479`, matching the build. Moved to `test me`.

## comment 5550126741 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126741

Created: 2026-08-06T19:07:34Z; updated: 2026-08-06T19:07:34Z

Exact metadata: [source record](sources/comment-5550126741-d64af92f4fb6f043d5b5d9abac14890a01e4c1236a57a83c8a06efec254f77c8.json).

still not working.

## comment 5550126751 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126751

Created: 2026-08-09T11:07:10Z; updated: 2026-08-09T11:07:10Z

Exact metadata: [source record](sources/comment-5550126751-563b458fb1bc2d8c7e2d69026625f98e471ace995481924f58048f9d86dd71c9.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53. The Ancient Tomahawk controller now arms from throwable ammo loss, observes Rockstar's live projectile lifecycle plus object/pickup signals, restores the ammo charge on impact, and remains separate from delayed unique recovery. Test ground, tree/wall, and ped impacts.

## comment 5550126767 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126767

Created: 2026-08-10T04:35:35Z; updated: 2026-08-10T04:35:35Z

Exact metadata: [source record](sources/comment-5550126767-f10db7efa285c79591d011bffce3a1d888c5b982ff8aa7fbe85b25d808a95a55.json).

Crash isolation found that mere ownership was incorrectly treated as holding the Ancient Tomahawk, causing idle projectile polling and repeated world-pool baselines while unarmed. The controller is now dormant unless the weapon is equipped, was equipped on the previous tick, or a throw is armed; baselines refresh only on equip/charge restoration, and the idle heartbeat performs no pool scan. The next live log confirmed monitoring=0 and equipped=0 while unarmed. Installed normal ASI: 80105728F13BBD3CAC5D54832B252744018461DFDE296F9A52B93CC3043806CF. Remains test me; impact return itself still needs runtime confirmation.

## comment 5550126781 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126781

Created: 2026-08-10T06:21:29Z; updated: 2026-08-10T06:21:29Z

Exact metadata: [source record](sources/comment-5550126781-d7a4ea4342af3f7b39c62729a085852ca9ba183391a42ed3e47d4e4bc3fe717d.json).

Progress -- in a sense.
Yet, it instantly and silently gets added to my inventory when I throw it.
But it also remains in the world. The weapon icon on the map, the "you can't carry any more of this item" when you get near, the fact you can physically still see it's there while simulatneously being in your inventory...
Can you not just delete it from the world as soon as it impacts, which would fix all this?
Also, the re-adding to your inventory shouldn't be silent. I'd like to see it in the acquisition log when you get it back!

## comment 5550126795 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126795

Created: 2026-08-10T07:16:49Z; updated: 2026-08-10T07:16:49Z

Exact metadata: [source record](sources/comment-5550126795-b5b07cbc5e85faae64c8dcad3dc3ba1fcecaf558039ac2abfabc14a1a94f369e.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test Ancient Tomahawk return after impact, no duplicate world copy, and acquisition feed.

## comment 5550126815 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126815

Created: 2026-08-10T08:42:25Z; updated: 2026-08-10T08:42:25Z

Exact metadata: [source record](sources/comment-5550126815-6753916d5e2d1288950da4a6145804f5c4bb5eea66c6d214ad784c4a083a6b0c.json).

Did you actually do anything?
- No acquisition feed
- Icon is clearly still there on the map
- Tomahawk is clearly still there in the world

<img width="554" height="655" alt="Image" src="https://github.com/user-attachments/assets/3a9f20d0-cd48-4639-8092-e764a9bedff0" />

## comment 5550126828 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126828

Created: 2026-08-10T10:58:58Z; updated: 2026-08-10T10:58:58Z

Exact metadata: [source record](sources/comment-5550126828-47f81dae8ccac0efc1b99cc46a94c4b0e57d9cb9deffbce70a99585d9f56817b.json).

this is like the 12th thing in a row you have completely failed to fix.

## comment 5550126841 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126841

Created: 2026-08-10T12:16:03Z; updated: 2026-08-10T12:16:03Z

Exact metadata: [source record](sources/comment-5550126841-f755c0667a75bcd8ecf2e38c97bf623e8d6fc108fdd5f4a72aae6d8868efe8e7.json).

stop marking things as actionable for no reason

## comment 5550126852 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126852

Created: 2026-08-10T15:08:12Z; updated: 2026-08-10T15:08:12Z

Exact metadata: [source record](sources/comment-5550126852-88005641eaa4ff630079b699c74899b18dff67fdf0bd54af9ba96767aa7e53cd.json).

Threw it into a wall. Immediately disappeared right back into my inventory. Threw it again. Clattered to the ground. Can't collect it even if I walk over it. It's over.
Come on, man.

## comment 5550126862 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126862

Created: 2026-08-10T16:33:23Z; updated: 2026-08-10T16:33:23Z

Exact metadata: [source record](sources/comment-5550126862-7d705fca75b5ae5767f9cec596a1c9646e413fa400822d3fb7f9db072bfcb5a4.json).

The version you tested still did its cleanup only on the impact frame. That was the defect: Rockstar can materialize the loose tomahawk/pickup and its map marker **after** that frame, and the inventory/ammo readback used for the acquisition feed can also lag the grant.

The installed replacement keeps the inventory return immediate, then watches the exact impact area for 2.5 seconds. During that bounded window it repeatedly removes only the new, unbaselined Ancient Tomahawk pickup/loose object, preserves the original world spawn and attached held prop, and waits for positive weapon+ammo readback before posting exactly one **Ancient Tomahawk returned** acquisition feed.

Please test three impacts: ground, wall/tree, and ped. Each must return immediately, leave no visible world copy or map icon, and show one acquisition-feed entry. This is now `test me`, not `actionable`, because that replacement is installed but those in-game outcomes are not yet confirmed.

## comment 5550126872 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126872

Created: 2026-08-10T19:15:09Z; updated: 2026-08-10T19:15:19Z

Exact metadata: [source record](sources/comment-5550126872-266a41eee0ae4f14a68b5bf6953b739fe2b8cfabb3da13894a64465723bb3515.json).

Now we've only gone backwards. I didn't even pick it up once this time.
What does the log say?

## comment 5550126886 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126886

Created: 2026-08-10T23:42:05Z; updated: 2026-08-10T23:42:05Z

Exact metadata: [source record](sources/comment-5550126886-c0a9eb1fc95a6aaff4cf051500088fd0ce3196e408b91590dc6b49640e329e52.json).

The retained log after your test says the Lexer-Lux/Lexeditor#164 updater ran, but it never saw an Ancient Tomahawk pickup, equip, or throw at all:

- `owned=1`, `ammoWeapon=1`, and `ammoType=1` from the first heartbeat through 16,078 ticks;
- `everArmed=0` throughout;
- `currentWeapon` was only `WEAPON_UNARMED` (and once `WEAPON_KIT_BINOCULARS`), never `WEAPON_THROWN_TOMAHAWK_ANCIENT`;
- therefore there is no `launch`, impact, return, cleanup, or feed line.

So the impact-return code did not run and did not delete the pickup in this session. The upstream contradiction is that Rockstar reported the Ancient Tomahawk as already owned with one charge while you could not actually pick/equip it. I am keeping Lexer-Lux/Lexeditor#164 `actionable` and investigating that ownership/loadout mismatch; I am not going to claim the delayed-cleanup change failed or passed from a throw the log never observed.

## comment 5550126901 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126901

Created: 2026-08-10T23:54:30Z; updated: 2026-08-10T23:54:30Z

Exact metadata: [source record](sources/comment-5550126901-d59200be34a587ffa867dc9f3c24c4bb6859548b18e5b5e99f3db56ad7507a44.json).

The repaired build is installed. The missing observation was upstream of the impact/cleanup code: Rockstar's current-weapon hash never exposed the Ancient Tomahawk in your retained test, even though inventory reported it owned with one charge.

The detector now also reads the actual held weapon entity and opens the exact projectile observation window only when that entity's model is `w_melee_tomahawk02`. It retains that observation for one transition frame so the engine cannot hide the throw between held-prop and projectile states. It still does **not** use `IS_PED_SHOOTING`, and it does not run global object/pickup scans merely because the tomahawk is owned.

Please test the initial pickup/equip, then throw it at ground, wall/tree, and a ped. The log now records the held entity/model, projectile edge, returned inventory charge, delayed world-copy cleanup, and acquisition feed separately, so one failed case should identify the failed stage instead of requiring another blind rewrite.

## comment 5550126921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126921

Created: 2026-08-11T02:24:49Z; updated: 2026-08-11T02:24:49Z

Exact metadata: [source record](sources/comment-5550126921-ca6d0a6961db61652e5f2f1eb13a02234ddba6a546a29e1869febd1c3f30e7ac.json).

No change.
WTF is going on? You literally had it working for a brief moment.

## comment 5550126937 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126937

Created: 2026-08-11T04:54:57Z; updated: 2026-08-11T04:54:57Z

Exact metadata: [source record](sources/comment-5550126937-07360eedd2201d3a803b70e0585ae0c87125b6dd08222f2bdf6700894438fb41.json).

I throw it. It comes back to my inventory on impact.
But the icon of the ancient tomahawk I've thrown remains on the map. The item itself remains there.
I'm getting really tired of this. I clearly saw you do it right before. It should not take me this much exasperation and time wasted for you to eventually get this right.
Keep doing it. You can do it. Please do it right.

## comment 5550126951 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126951

Created: 2026-08-11T09:32:29Z; updated: 2026-08-11T09:32:29Z

Exact metadata: [source record](sources/comment-5550126951-5702bfcf4cedaf80a22ced37f0733f55c55f22fe5e0aa6ea3ca1aeb42ee19d7e.json).

The cleanup used player position when the settled projectile had no position, then ignored returned copies more than 5 m away. It also refreshed the baseline during cleanup and could bless a late copy. Cleanup now protects the original baseline once and removes every new loose Ancient Tomahawk object/pickup from that throw, regardless of distance. Test ground, wall/tree and ped impacts.

## comment 5550126963 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126963

Created: 2026-08-13T06:58:53Z; updated: 2026-08-13T06:58:53Z

Exact metadata: [source record](sources/comment-5550126963-6614203bfcb158b43af4f2623c3d39a465d52fdb8c71a82f5e430542cd32b91c.json).

now we're just back to where we were like 10 tries ago: the first throw sends it right back to my inventory. every single throw after that doesn't.
and there's still no acquisition log popup.

## comment 5550126973 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126973

Created: 2026-08-14T01:23:09Z; updated: 2026-08-14T01:23:09Z

Exact metadata: [source record](sources/comment-5550126973-bc6e94ec53413545760975f8413246f1b9b3f9dcacd73e4e43c421af0b2b8ea7.json).

**"First throw works, every one after doesn't" had a specific cause, and I found it.**

The module decides a tomahawk has come back by finding a world object or pickup that is **not** in its baseline — the set it treats as already existing. That baseline is refreshed in only two situations: when you newly equip the weapon, and when a charge is restored. Both are additionally gated on the cleanup window being closed.

Here is the trap. The returned charge arrives **during** the cleanup window — that window *is* when the weapon is handed back. So `chargeRestored` fires while cleanup is still active, and the refresh is skipped. By the time the window closes, the ammo already equals its previous value and the weapon has not changed, so neither condition can ever fire again.

**The baseline therefore keeps the first throw's handles forever.** RDR2 pools and recycles object and pickup handles, so the second throw can be handed a handle that is still sitting in that stale set. It reads as pre-existing, no fresh pickup is ever found, and the return never fires. Exactly once working, then never again — and it would look identical no matter how many times you threw it.

Fixed by rebuilding the baseline at the moment the cleanup window closes. That is the one instant where nothing is in flight: the returned copy has already been removed and the next throw has not started. It is a third, separate reason to refresh rather than a change to the existing two, because their original purpose — not absorbing a tomahawk already stuck in a tree — still holds. It logs `baseline rebuilt after return` each time, so you can see it happen.

Its verifier passes and it is installed.

**On the missing acquisition popup:** not addressed. The code posts a return feed item (`returnFeedPosted`), but I have no evidence about whether it fires, because your session had `owned=0 everOwned=0` throughout — you never had the weapon equipped, so there is no throw data at all in the log. Once you throw it a few times the log will show `feedPosted=` and I can work from that instead of guessing.

Test: throw it at the ground, then throw it again, then a third time — the second and third are the ones that matter. Also try a wall and a ped.


## comment 5550126991 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/164#issuecomment-5550126991

Created: 2026-08-14T06:01:49Z; updated: 2026-08-14T06:01:49Z

Exact metadata: [source record](sources/comment-5550126991-ccdccf400627113006b61dca396f09ea735be13e14c86408798f2217f54fa73e.json).

**Verified the fix is actually wired, and why your last session showed nothing.**

Today I have found several "shipped" fixes that were dead code, so I checked this one end to end rather than trusting the previous comment. It is complete:

- `baselineRefreshDue` is set when the cleanup window closes (`:326`)
- consumed on the next settled tick, rebuilding the baseline only when the weapon is not armed and cleanup is no longer active (`:495`)
- cleared on the competing path (`:435`)

That is the exact trap described last time — the returned charge arrives *during* the cleanup window, so the old refresh conditions could never fire and the first throw's handles stayed in the baseline forever, making every throw after the first read as "nothing new returned". The module is present in the installed binary.

**Why there is still no result:** your entire session reads `owned=0 everOwned=0 everArmed=0 monitoring=0`. You did not have the Ancient Tomahawk on you at any point, so the return path never ran once. Nothing in the log confirms or denies the fix.

Moving to `test me` since it is built, installed and waiting on you rather than on me.

Test: throw it at the ground and at a person, several times in a row. It should come back **on impact**, immediately, every throw — not after a delay, and not only the first time. The heartbeat reports `owned/everArmed/monitoring/baselineObjects/baselinePickups`, so if a later throw fails to return, that line says whether the baseline was rebuilt between throws.

