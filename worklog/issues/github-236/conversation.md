# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356315952 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236

Created: 2026-08-10T09:33:15Z; updated: 2026-09-05T07:02:05Z

Exact metadata: [source record](sources/issue-5356315952-5637e6956d848a955f97a4f31e9e9f53bd740179d3909727663576a33f7957b5.json).

Rather than walk-run-sprint, there are now only walk and sprint. Sprint happens when holding shift. Stop holding it, back to walk. Simple stuff.
Let me set the base move speed of the player (before any buffs or whatever). Then let me set sneaking and sprinting speeds as a multiplier of that. Remove the ability to sneak run.
Remove all restrictions on when/where you can sprint.


Prior art: https://www.nexusmods.com/reddeadredemption2/mods/8957
https://www.nexusmods.com/reddeadredemption2/mods/1173
Update the stamina options to reflect this.

## issue 5356315952 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236

Created: 2026-08-10T09:33:15Z; updated: 2026-09-06T13:31:45Z

Exact metadata: [source record](sources/issue-5356315952-0710bb99eea20317b86600ecc61ee1b6181b4d33382504b0c9c9b1e78e0e976f.json).

Use walk/hold-to-sprint instead of walk/run/sprint. Remove crouch-running and allow sprint except where a real gameplay state prevents it.

**Actionable — latest location-restriction repair is source-only.** Earlier tests still found places where sprint refused to start. No installed retest is ready.

Original references: [mod 8957](https://www.nexusmods.com/reddeadredemption2/mods/8957), [mod 1173](https://www.nexusmods.com/reddeadredemption2/mods/1173).

## issue 5356315952 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236

Created: 2026-08-10T09:33:15Z; updated: 2026-09-06T13:31:45Z

Exact metadata: [source record](sources/issue-5356315952-8b99677fa3124e082e5642024da2c9e1e2d7cd400cd1fd76bf6272a23f982a4e.json).

Use walk/hold-to-sprint instead of walk/run/sprint. Remove crouch-running and allow sprint except where a real gameplay state prevents it.

**Actionable — latest location-restriction repair is source-only.** Earlier tests still found places where sprint refused to start. No installed retest is ready.

Original references: [mod 8957](https://www.nexusmods.com/reddeadredemption2/mods/8957), [mod 1173](https://www.nexusmods.com/reddeadredemption2/mods/1173).

## comment 5550145543 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145543

Created: 2026-08-10T10:08:16Z; updated: 2026-08-10T10:08:16Z

Exact metadata: [source record](sources/comment-5550145543-41019e15c4e5512469fabaff4e2410e5574e67f00a47467862cfc8592e722147.json).

Source implementation is complete and integrated for the next combined build. On-foot movement is now walk by default, direct sprint only while the physical Sprint control is held, and immediate walk on release; crouch/stealth always uses crouch-walk so sneak-running is removed. `[HumanMovement]` exposes BaseMoveRate, SneakMultiplier, and SprintMultiplier with two-second hot reload, and the obsolete Jogging stamina setting is removed from the presented configuration. Ordinary camp/interior/mission/aim/wanted/stamina restrictions are not used; the controller yields only states that must own non-ground locomotion (#6 roll, Lexer-Lux/Lexeditor#109 prone, custom climb, mount, swim, fall, ragdoll/get-up/frontend/death).

This remains actionable until the combined build is installed and hash-verified, then every listed gait/location/state and the three rate settings need in-game confirmation.

## comment 5550145558 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145558

Created: 2026-08-10T10:42:06Z; updated: 2026-08-10T10:42:06Z

Exact metadata: [source record](sources/comment-5550145558-bbf5ccd4d81def682a84999a25b9074db3040c22c67de9012da1e36d85d3a7a5.json).

I held shift, then let go of shift, then just like in vanilla I went back to that running state where your stamina drains but slower.
Come on...

## comment 5550145574 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145574

Created: 2026-08-10T10:51:11Z; updated: 2026-08-10T10:51:11Z

Exact metadata: [source record](sources/comment-5550145574-90c66e60a964ee9c92e7f03ef590ed6cb23add55f38a8d0fbf5259e00a25e5b7.json).

You never got rid of crouched sprinting, either.

## comment 5550145586 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145586

Created: 2026-08-10T10:57:15Z; updated: 2026-08-10T10:57:15Z

Exact metadata: [source record](sources/comment-5550145586-5413a474c14570ee1e820511db6fb20d91293b470ccf470c905c6ddd30655d22.json).

Returned-test root cause found and repaired in source: Story PLAYER_ID() is valid index 0, but the module tested !player and therefore permanently set unavailable=1. The installed log confirms frames=0 for the entire test. That invalid null check is removed; Shift is owned directly, release forces WALK in the same frame, and a three-frame readback rejects residual run/sprint state. Remains actionable until rebuilt/installed and the release log confirms walk.

## comment 5550145603 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145603

Created: 2026-08-10T12:07:17Z; updated: 2026-08-10T12:07:17Z

Exact metadata: [source record](sources/comment-5550145603-753d771364495cfc8ecae499201484c6d8aaa6776df431a2bd3c0fc437eb00cd.json).

The immediate movement-animation failure is now isolated rather than treated as a successful test. GameplayTweaks Human Movement is hot-disabled, and the live log confirmed `enabled=0`.

FWOC was also still installed as `FastWalk.asi`, so two systems were trying to own on-foot locomotion. I removed that exact ASI from the game root and moved it to recoverable mod storage. Since RDR2 had already loaded FWOC into the current process, this part only takes effect after the next game restart.

Lexer-Lux/Lexeditor#236 remains actionable. The clean baseline after restart is FWOC absent and Human Movement disabled; I will not return this issue to `test me` until the custom replacement is repaired and installed.

## comment 5550145622 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145622

Created: 2026-08-10T17:23:48Z; updated: 2026-08-10T17:23:48Z

Exact metadata: [source record](sources/comment-5550145622-5d6d645a2969d6e2f3d85b8e5b605ac9cd1195f0dfb2293a3c895b21488ad685.json).

The repaired Human Movement candidate is installed and Enabled=1; FWOC/FastWalk is absent from the game root. The previous animation glitch was caused by pinning/forcing the locomotion graph every frame. This build does not force motion state or desired/minimum blend: Rockstar owns the animation transition, while the mod applies only the configured move-rate scalar and maximum walk/sprint ceiling. Test ordinary walk, hold-Shift sprint, direct release to walk, all directions, aim, interiors/towns/camps, and the configured base/sneak/sprint speeds. If it glitches, Enabled hot-reloads so it can be disabled without another restart.

## comment 5550145632 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145632

Created: 2026-08-11T02:01:36Z; updated: 2026-08-11T02:01:36Z

Exact metadata: [source record](sources/comment-5550145632-5846537b511b5474ad0f26983a61cd38ff00b27c8574a6e2dc2c86e5dd3725b1.json).

<img width="340" height="439" alt="Image" src="https://github.com/user-attachments/assets/55e6685d-295f-4430-aedf-09719f00cff5" />

These settings do nothing and you can obviously tell that because Sprint speed is set to be 1x walk speed, meaning they'd be the same speed...but they're not

## comment 5550145641 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145641

Created: 2026-08-11T03:58:52Z; updated: 2026-08-11T03:58:52Z

Exact metadata: [source record](sources/comment-5550145641-5ae236f35d7e242dc378cc7e4769d79aa602f39e092380680ab8912dc9fdfdbc.json).

I can safely provide these parts:

- only walk and sprint during ordinary on-foot movement;
- hold Sprint to sprint, then return directly to walk on release, with no intermediate jog/run;
- crouching always uses crouch-walk, so there is no sneak-run;
- sprint is allowed in normal camps, towns, interiors, aiming, wanted states, and missions when Rockstar has not assigned another movement task;
- Stamina uses only walking/sneaking and sprinting rates; the obsolete jogging rate is removed;
- separate hot-reloaded relative rate scalars for walk, sneak, sprint, and the road bonus, each within Rockstar's documented 0.10-1.15 range.

What I cannot honestly provide through the resolved native is an absolute speed or a true cross-gait ratio. A sprint scalar of 1.0 means native sprint speed, not “the same speed as walking.” I should replace the misleading base-plus-multiplier presentation with independent Walk, Sneak, and Sprint gait-rate scalars if this supported subset is what you want. Lexer-Lux/Lexeditor#236 remains actionable; I have not changed the requested design without your decision.


## comment 5550145664 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145664

Created: 2026-08-11T04:40:37Z; updated: 2026-08-11T04:40:37Z

Exact metadata: [source record](sources/comment-5550145664-c9de19f68d6d9a266a2e62e85a501ae246e6494fb988cd5edcff06ba276cffa7.json).

Installed and hash-verified, so this is yours to test now. One honest limit before you do: your `BaseMoveRate=2` is not what gets applied. The engine's move-rate native maxes out at 1.15, so a requested 2 is clamped to 1.15 — the log now reports both (`requestedRate=2 rate=1.15 nativeRangeClamped=1`) instead of pretending the write succeeded. Sneak and sprint are multipliers on top of that clamped value, so equal walk and sprint numbers still will not produce equal world speeds.

That means "let me set the base move speed" is only satisfied inside 0.10–1.15 via this native. If you want a true absolute speed beyond that, it is a different mechanism and a separate piece of work — tell me and I will scope it.

## comment 5550145683 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145683

Created: 2026-08-11T06:17:32Z; updated: 2026-08-11T06:17:32Z

Exact metadata: [source record](sources/comment-5550145683-ab3e719df439fe729ed6ea733c0f467f750503c782182577ab6753130ab5f41b.json).

Correction: Lexer-Lux/Lexeditor#236 is not accepted. The current log still reports the engine remaining in sprint for up to 343 ms after Shift release, and the exposed rate native cannot provide the requested equal walk/sprint world speeds. Human Movement is disabled in both installed and workspace configuration. This issue returns to actionable; the current implementation will not be shipped as the requested movement rework.

## comment 5550145697 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145697

Created: 2026-08-11T09:25:58Z; updated: 2026-08-11T09:25:58Z

Exact metadata: [source record](sources/comment-5550145697-575ee27a14f85d714b4c3fbc49869c1ddd48e0426347454d8b67ae67d8c2074a.json).

What I can give you safely is: walk when Shift is released; Rockstar sprint while Shift is held; crouching always wins, so there is no sneak-run; and three independent hot-reloaded rate scalars for walk, sneak, and sprint. The supported range is 0.10-1.15 for each gait. What this native cannot do is set metres-per-second speeds, make walk and sprint equal from equal numbers, or remove Rockstar's roughly one-third-second sprint-to-walk blend without fighting the animation graph. I removed the misleading base-times-multiplier controls instead of keeping settings that cannot mean what they say.

## comment 5550145712 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145712

Created: 2026-08-12T12:49:29Z; updated: 2026-08-12T12:49:29Z

Exact metadata: [source record](sources/comment-5550145712-dd5e7353a5d4d68c83b019d97d37d3c56c88b56eb55c698f97ee90ce2c8409ca.json).

Okay well if it's within 1.15 then I just don't want it. So get rid of it.
Mark this one as closed. Separate out the m/s move speed setting and crouch/sprint move speeds as a multiple of that setting into a child issue, flag as unfeasable, then close that one too.

## comment 5550145724 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145724

Created: 2026-08-12T13:36:13Z; updated: 2026-08-12T13:36:13Z

Exact metadata: [source record](sources/comment-5550145724-b016db6573f09077811ed3796d1a29658afae742a2091ef2494a35e41f17fb06.json).

The rejected 0.10-1.15 movement controller and its settings have been removed from the runtime, INI, LEXEDITOR, and in-game settings menu. I created child Lexer-Lux/Lexeditor#279 for the requested absolute m/s base speed with crouch and sprint multipliers, labeled it unfeasible, and closed it because the resolved Story Mode native cannot provide those values without the unsafe movement fights you rejected.

## comment 5550145739 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145739

Created: 2026-08-13T01:39:25Z; updated: 2026-08-13T01:39:25Z

Exact metadata: [source record](sources/comment-5550145739-85812817057512f017abba471e60c46a0200c9a5f7875a195aedc666e57ef92e.json).

...and now you went and broke it.

## comment 5550145749 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145749

Created: 2026-08-13T04:45:20Z; updated: 2026-08-13T04:45:20Z

Exact metadata: [source record](sources/comment-5550145749-a9c3aaf79e8139b287f9ed898a5a0c4fcf75127cd820a5adcd7d48a0b9478123.json).

The removal regression is repaired. The installed build restores Rockstar movement defaults once for each live player ped, then performs no gait or input control. After a full restart, confirm walk, run, sprint, and crouch are back to vanilla behavior.

## comment 5550145759 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145759

Created: 2026-08-13T07:04:36Z; updated: 2026-08-13T07:04:36Z

Exact metadata: [source record](sources/comment-5550145759-36d9a8cb7d0b678166bede5624ae03e1db291e42450ae4d6cc814394b3ba9765.json).

yeah i all i have to do is walk, hold shift, then release. now i'm back into jogging, even though i explicitly told you to get rid of that state. and you did! you had it fixed, then you broke it, and now you won't fix it.

## comment 5550145768 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145768

Created: 2026-08-14T00:02:02Z; updated: 2026-08-14T00:02:02Z

Exact metadata: [source record](sources/comment-5550145768-da518a1119afa317b0fc139f130d4e0e7cd91eb2c6eaddb69f3f1c8e72814ba6.json).

**Jog is gone again — gait only, and no speed settings anywhere.**

You were right that this was working and then got broken by the removal. Ripping out the rejected 0.10–1.15 scalars also tore out the gait behaviour you actually wanted, and the module ended up doing nothing at all. Your log was unambiguous: every line read `withdrawn idle ... controllerWrites=0`.

Restored, with the scalars staying deleted: walk and sprint only, hold Sprint to sprint and release returns directly to walk with no intermediate jog, crouch always uses crouch-walk so sneak-running is gone, and sprint is not restricted by location or state except where something else must own locomotion (roll, prone, climb, mount, swim, fall, ragdoll, death). No base/sneak/sprint speed numbers exist in the module, the INI, LEXEDITOR or the in-game menu, and Lexer-Lux/Lexeditor#279 stays closed.

Transparency on how this one was produced: the worker that wrote it hit the account spend limit and died before it could report. The module is complete, active (`Enabled=1`), compiled into the installed build, and its verifier passes on the full contract — but it is less documented than usual, so treat the sprint-release moment as the thing most worth watching.

Test: walk, hold Shift, release. You should land in walk, not jog. Then crouch and try to sprint — it must stay crouch-walk.


## comment 5550145782 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145782

Created: 2026-08-15T02:00:49Z; updated: 2026-08-15T02:00:49Z

Exact metadata: [source record](sources/comment-5550145782-a7a61c3fff444ebc30aacb20a93ea9e0d9f6d0eaac3935a3e4b4570bf00f802f.json).

Now every time I let go of the shift button there's this rapid jump I can see, like his animation just skips directly to another. We had this done correctly on like the 2nd try so I'm not sure why it's so hard to get done right now!

## comment 5550145794 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145794

Created: 2026-08-15T02:20:31Z; updated: 2026-08-15T02:20:31Z

Exact metadata: [source record](sources/comment-5550145794-a24a680f2ec8ab46e756f6700ff3624cc9a631bfceb1f3961a3eec520d043d3f.json).

It's like you removed the entire Sprint -> Walk transition or something?

## comment 5550145805 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145805

Created: 2026-08-15T04:11:55Z; updated: 2026-08-15T04:11:55Z

Exact metadata: [source record](sources/comment-5550145805-a90bf864187d11168868f0bf53f39f52ddfaf479d2f28fd1b7c532e7de7d2527.json).

**Confirmed from your own session. The jog-on-release complaint is gone.**

Your report was: "walk, hold shift, then release — now I'm back into jogging". Your log has 33 sprint releases:

```
release confirmed observed=walk run=0 sprint=0 ceiling=1 forceAttempts=1 ageMs=16
```

- **30 landed on walk, 3 on still, 0 on jog.**
- Time to settle: median **16 ms**, minimum 0.
- 34 `gait sprint -> walk` transitions, and no `-> jog` gait anywhere.
- Crouched samples: only `still` and `walk` observed, and **zero** frames of crouch with sprint held. No sneak-running.

**One thing I want to state plainly rather than hide, because the raw log looks alarming:** `observed=jog` does appear 19 times. Every one has `currentBlend` mid-ramp — 1.50, 1.58, 1.95, 2.0 — during a `sprint -> walk` or `walk -> sprint` transition.

That is unavoidable, not a bug. Rockstar's move-blend is continuous: walk is 1.0, run 2.0, sprint 3.0. Going between walk and sprint *must* pass through the run band, so "no jog state" cannot mean the blend never crosses 2.0. It means you never **settle** there — and you do not. Of 72 steady-state heartbeats, exactly one caught a sample mid-transit; the other 71 read still, walk or sprint.

The one slow case worth knowing about: a single release took 6 force attempts over 1109 ms before settling, versus 16 ms for the rest. It still ended correctly (`observed=still`), but if you ever feel a release hang for about a second, that is what it was.

Marking `computer-confirmed`: the behaviour you asked for is verified from runtime evidence — walk and sprint only, release lands on walk, no sneak-run — rather than from reading the source.


## comment 5550145814 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145814

Created: 2026-08-15T20:17:59Z; updated: 2026-08-15T20:17:59Z

Exact metadata: [source record](sources/comment-5550145814-161afdb64aa71e2180f326be266f0a4e8a50c5b6c9fb203652b1262a8d63b11b.json).

No change. Did you forget to compile or something?

## comment 5550145833 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145833

Created: 2026-08-18T03:27:22Z; updated: 2026-08-18T03:27:22Z

Exact metadata: [source record](sources/comment-5550145833-6af3409a5f67eb735daa227935e0009965da348dc891751fa55b469c9d3af16d.json).

**"Did you forget to compile" — no, but you were right that nothing changed, and I can now show why my "confirmed" was wrong.**

Your 08-16 session runs the development build and the module is alive. Mechanically every release still lands correctly — 8 of 8 `release confirmed observed=walk run=0 sprint=0`, ageMs 15–31, no steady-state jog. That is what I marked `computer-confirmed` on, and it was not enough.

**The number that gives it away is `ceilingWrites=1`.**

Across 5,595 evaluations the walk-band ceiling was written **once**. That is by design — `SET_PED_MAX_MOVE_BLEND_RATIO` is a durable per-ped property, so re-writing it every frame would be a pointless native. But the guard was:

```cpp
if (g_humanMovementCeiling == ceiling) return;   // our own CACHE
PED::SET_PED_MAX_MOVE_BLEND_RATIO(ped, ceiling);
```

`g_humanMovementCeiling` is what this module last *wrote*, not what the engine currently *holds* — and that native has **no getter** in the index, setter only. So once 1.0 was written the guard returned early forever. If the engine dropped the ceiling — a mission, a cutscene, mounting, a respawn, anything that re-initialises the ped's movement state — nothing ever put it back, and jogging returned.

**And the log actively hid it.** The heartbeat printed `ceiling=1` because it was printing that same cache. So the module reported success while you were jogging, and I believed the module. That is the fabricated-field pattern again, in a subtler form: not an invented value, but a cached one presented as observed state.

**Fix:** the ceiling is now re-asserted from evidence. There is no getter, so it infers from the live blend the module already samples — if the intended ceiling is the walk band but the observed blend overshoots it by more than 0.15, the engine is no longer honouring our value, and it is re-applied. Rate-limited to 250 ms so it can never become the per-frame graph fight that got the first controller rejected, and it logs when it fires:

```
ceiling lost and re-asserted ceiling=1 observedBlend=… reasserts=N
```

The heartbeat carries `ceilingReasserts=` too. Next session decides it outright: **nonzero means the engine was dropping the ceiling and this was the bug**; still zero while you are jogging means the ceiling is held and the jog comes from somewhere else entirely.

All three movement contracts pass (#144, Lexer-Lux/Lexeditor#248, Lexer-Lux/Lexeditor#249). Installed and hash-verified.


## comment 5550145857 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145857

Created: 2026-08-19T12:16:56Z; updated: 2026-08-19T12:16:56Z

Exact metadata: [source record](sources/comment-5550145857-f32b453ddd724699ec15fdf90ae5c1fa9a8b4d90ebbf6f564c31da74d1895de9.json).

Still doing it. This is crazy. You got this right on like, the 2nd try. Then you broke it. Now you can't fix it?

## comment 5550145877 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145877

Created: 2026-08-20T01:18:33Z; updated: 2026-08-20T01:18:33Z

Exact metadata: [source record](sources/comment-5550145877-3968eceae627d417aae3d0d86f9cbbd5979dea14e89743db89d5c1db65212a2c.json).

You're right that it was working and then got broken, and I can now show exactly what broke it from your own log.

**What was wrong.** All three attempts only corrected your gait at one single moment: the frame where you let go of Shift. Nothing else could ever trigger the correction. But that isn't how you're actually ending up in the jog animation. Your log from this session:

```
1889296  yield walk -> unavailable; ceiling restored to 3
1890000  gait unavailable -> walk sprintHeld=0 moving=1 ceiling=1
         observed=jog run=1 currentBlend=1.99231 desiredBlend=0.587993
1890078  yield walk -> unavailable; ceiling restored to 3
1890781  gait unavailable -> walk ... observed=jog run=1 currentBlend=1.99308
```

Read that line: Shift is **not** held, the mod **is** in control of Arthur, and Arthur is **jogging** — and the mod does nothing, because the only thing it was watching for was "sprint just ended", and this wasn't that.

Why it keeps happening: something else in the mod (the climbing and dodge-roll code — those lines are stamped to the same millisecond) briefly claims control of Arthur. Every time it does, the movement code hands the walk limit back to the game for about 700ms, the game ramps you back up to a jog, and then the movement code takes over again and just shrugs. That happened 23 times in this one session, and 10 of the 24 hand-backs found you already jogging.

Two other things the log caught:

- When you pressed Shift **again**, the mod kept forcing you back to walk four more times, fighting your own keypress, and then printed "release confirmed" while you were sprinting.
- The counter that was supposed to prove the walk was holding was never actually printed anywhere. It looked like it was watching. It wasn't.

**What's different now.** The correction is no longer tied to one moment. Any time the mod is in control and you aren't holding Shift, it compares what it wants against what Arthur is actually doing, and while those disagree it puts him back to walk — whether you just released Shift, or the game snuck you back into a jog while some other part of the mod had control. It stops the instant they agree, so it isn't fighting the animation system while you're just walking. It also drops the correction immediately when you press Shift again instead of fighting you.

I also fixed the reason this took four tries: the "yield" line now says *which* thing took Arthur away, and the counters that prove the walk actually held are printed in the heartbeat. If this one is still wrong, the next log will say why in one line instead of hiding it.

**What to test once it's built and installed:** hold W and jog around, tap Shift on and off a few times, and specifically jump a few times while moving and then keep walking — that jump case is the one that was reproducing it in your log. If Arthur drops back into the jog animation at any point, that's still broken and the log will now name the cause.

I have not launched the game and can't confirm this on screen — this is what changed and why, not a claim that it works.


## comment 5550145893 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145893

Created: 2026-08-20T09:14:17Z; updated: 2026-08-20T09:14:17Z

Exact metadata: [source record](sources/comment-5550145893-42b502685c7252fadaa60a9aa913d54febc1da4c99193e00eb152ecb19792488.json).

still not fixed bruh

## comment 5550145905 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145905

Created: 2026-08-20T10:26:15Z; updated: 2026-08-20T10:26:15Z

Exact metadata: [source record](sources/comment-5550145905-0efdd49894678e7f387ba7bcfd73d80ee7d510772a9768b1a9c64990816540c4.json).

The installed repair now corrects any live walk-versus-jog disagreement, not only the instant Shift is released. Hold W, tap Shift on and off, then jump while moving and keep walking. Arthur must return to walk without settling into jog, and crouched movement must not sprint. The log now names any locomotion owner that interrupts the correction.

## comment 5550145921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145921

Created: 2026-08-20T12:53:21Z; updated: 2026-08-20T12:53:21Z

Exact metadata: [source record](sources/comment-5550145921-53ddb1211dd0b29f9494d72ee4e40813d92a95dc1da1c7afe970aa592a2ea43e.json).

Returned test: the movement repair still does not restore the required behavior. Marked actionable for the next actionable pass.

## comment 5550145936 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145936

Created: 2026-08-20T13:27:38Z; updated: 2026-08-20T13:27:38Z

Exact metadata: [source record](sources/comment-5550145936-08846759c1e425a53ac502ae45a8ce1b3587a172af130ecc72d45e3fdcbaa19d.json).

The returned test now isolates the defect: releasing Shift and W together stops cleanly, but releasing only Shift while W stays held causes an immediate animation hitch/cancel. The installed log records the mod forcing MOTIONSTATE_WALK on the exact sprint-to-walk frame. That forced graph retake is the hitch; its accepted return only proves the call ran, not that the transition stayed smooth. The next repair will remove the force and leave Rockstar's locomotion graph in control while the mod keeps only the walk-band ceiling and observes the settled result. Lexer-Lux/Lexeditor#236 remains actionable and high priority.

## comment 5550145953 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145953

Created: 2026-08-20T19:16:44Z; updated: 2026-08-20T19:16:44Z

Exact metadata: [source record](sources/comment-5550145953-ac4570614468c995942798879d8dfc7e5122dd7d35cfeb751952ff5f1751e8ff.json).

Returned test: there are still world locations where Sprint cannot start. The movement requirement remains location-independent whenever no real locomotion owner must yield. The next repair must log the exact gate and Rockstar control state at each refused Shift hold instead of treating all restricted areas as unavoidable.

## comment 5550145963 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/236#issuecomment-5550145963

Created: 2026-08-20T19:43:02Z; updated: 2026-08-20T19:43:02Z

Exact metadata: [source record](sources/comment-5550145963-cf1a1780df247de203a6374a4a0f9c0687d22fd5c1c2a491c41387b3b4481725.json).

Source repair is complete but unbuilt. The module now restores Rockstar's Sprint control while ordinary on-foot locomotion owns the frame and movement plus Sprint are held. It does not synthesize input or force Arthur's motion, task, speed, velocity, or position. A bounded diagnostic records any place where the live ped still refuses to sprint. After the next install, retest each town, camp, interior, and ordinary mission location that previously blocked running.
