# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356301794 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179

Created: 2026-08-06T03:41:37Z; updated: 2026-09-05T06:59:01Z

Exact metadata: [source record](sources/issue-5356301794-6f78abd4d252d2269c1a9af2e1b2413f6ba212ea037a3e3c4bce8738a2ac17db.json).

Technically you did this but now my rifle just teleports instantly onto my back when I hit tab. But if I switch to my hands then I get this proper animation of him putting his rifle away, so why don't we just do it that way?

## issue 5356301794 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179

Created: 2026-08-06T03:41:37Z; updated: 2026-09-06T12:55:05Z

Exact metadata: [source record](sources/issue-5356301794-a1818589d2f37548fc70800367f3637b26a259ac95e4dd616c6317902940a286.json).

Tab should stow the held weapon with its normal animation, not become unresponsive or disable unrelated actions.

**Status: The latest repair is described but not confirmed installed.** It restores a working keyboard input and avoids taking Tab when the replacement cannot read it. Verify delivery before another tap/draw-transition test.

## comment 5550130118 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130118

Created: 2026-08-06T05:44:38Z; updated: 2026-08-06T05:44:38Z

Exact metadata: [source record](sources/comment-5550130118-ff7886d4b2f5e257c251a8e73bd159dc0851564046dc364ff7b961617abc4e07.json).

Implemented using Rockstar's animated stow sequence: non-immediate hide, select unarmed without forcing, then TASK_SWAP_WEAPON in stow mode. Combined ASI build passes and hash-verified install is queued for RDR2 exit, so this remains actionable until it lands.

## comment 5550130128 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130128

Created: 2026-08-06T06:49:20Z; updated: 2026-08-06T06:49:20Z

Exact metadata: [source record](sources/comment-5550130128-845e773239d09468c591cd7d7dd8698f743b2726b448e0be7e10d6de9768073a.json).

still teleporting onto my back.

## comment 5550130135 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130135

Created: 2026-08-06T07:19:03Z; updated: 2026-08-06T07:19:03Z

Exact metadata: [source record](sources/comment-5550130135-605aa8dcff348a9b241f4e18b1daeb6a6b04432ee7cb3f4f0edf5ac8ae39a363.json).

Built and installed. The mod now intercepts Tab only while a weapon is actually in hand, preventing vanilla's same-frame instant back attachment while preserving normal empty-hand draw. Please test rifle/repeater stowing on foot, plus drawing again from empty hands.

Installed ASI SHA-256: `85C62841F5F6C8C5B2D069A0965D3AAFA703095B9B0B74876E7728BFE5ED5D32`

## comment 5550130143 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130143

Created: 2026-08-06T07:33:32Z; updated: 2026-08-06T07:33:32Z

Exact metadata: [source record](sources/comment-5550130143-74dff9484bd32544070a87d1770c0a7fc0909bc20d19a52e9859504ec077f744.json).

this is so weird. i have to tap tab like 50 times for it to actually put away. i think it once went away the way i want, then the next time he put it into his hand like in vanilla, then AFTER put it onto his back.
please tell me you didn't do some retarded shit like going back to the timeout based method.

## comment 5550130156 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130156

Created: 2026-08-06T09:18:57Z; updated: 2026-08-06T09:18:57Z

Exact metadata: [source record](sources/comment-5550130156-400ec1d79d8019e45bf20cd9e3a3bcbd9b58f859760ab11515c1aa6f91b8968f.json).

Correction: your report that Tab still required repeated presses and produced inconsistent hand/back behavior was never addressed by the later deployment comments. This is back in actionable until that exact behavior is fixed.

## comment 5550130178 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130178

Created: 2026-08-06T11:24:47Z; updated: 2026-08-06T11:24:47Z

Exact metadata: [source record](sources/comment-5550130178-578683d36ede17cc52a47bf646852a80eaf5419a7c41d2934069f799eb08cd96.json).

it's still not fixed.

## comment 5550130187 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130187

Created: 2026-08-06T13:00:23Z; updated: 2026-08-06T13:00:23Z

Exact metadata: [source record](sources/comment-5550130187-c644db85e703e81e923e1478bd49d8ff09f5da5d85fafe372aeef6a9dfba1cad.json).

still not fixed.

## comment 5550130200 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130200

Created: 2026-08-06T14:42:17Z; updated: 2026-08-06T14:42:17Z

Exact metadata: [source record](sources/comment-5550130200-50a74ac2486476843c3591882cc6ba23ce2d9143519cd553db1bf7f940c0b486.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Press the physical holster action once with a weapon in hand; confirm one authored stow and no immediate redraw/retry loop.

## comment 5550130213 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130213

Created: 2026-08-06T18:51:55Z; updated: 2026-08-06T18:51:55Z

Exact metadata: [source record](sources/comment-5550130213-f252216daa13fd19b4e48a6d1104077b0453510c4ef1b08b41b3971886aff492.json).

So close. But I think I found the cause of tab not working -- it's actually that there seems to be this time period after i pull out my weapon during which i can't put it away? is that really necessary? can we not get rid of it?

## comment 5550130226 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130226

Created: 2026-08-09T09:06:15Z; updated: 2026-08-09T09:06:15Z

Exact metadata: [source record](sources/comment-5550130226-99318ff84ef1b095197fd8a4cc706e776d49ebe64c911f31b377be0db0306f29.json).

can this not be fixed? was it in vanilla? i feel like this wasn't.

## comment 5550130239 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130239

Created: 2026-08-09T09:50:34Z; updated: 2026-08-09T09:50:34Z

Exact metadata: [source record](sources/comment-5550130239-5d87ccc33acee15069c51fd44009184e9d2497692dcde98d5eba8d80e53901cf.json).

Third-pass high-priority research result:

**Direct answer:** no fixed vanilla post-draw holster cooldown was found. Rockstar serializes draw and stow through the same script task, so a restow requested during an active draw must wait for that task to retire, but the current mod is dropping presses *before* its task-state wait can handle them.

### What the live session proved

The captured Aug. 9 release session contained:

- 70 `press rejected gate=controlLocked`
- 47 `press rejected gate=emptyHand`
- only 4 accepted/issued/survived presses
- **zero** `defer: swap task busy`

Several rejected real Tab presses occurred while the module reported `armed=1`, `pending=0`, and swap-task status `8` (finished/idle). Therefore those failures were not caused by a live draw task or by a timeout. The exact owner of the disabled aggregate PAD action was not logged; some rejects overlapped the weapon wheel and one binocular transition, so it would be wrong to blame every reject on one system.

The source explains the loss:

- `GameplayTweaks/modules/always_holster.cpp:162-176` rejects the press whenever `IS_CONTROL_ENABLED(INPUT_TOGGLE_HOLSTER)` is false, before the disabled-control edge can be accepted and before pending task-state deferral.
- `:168-171` also rejects while attach point 0 is still empty, so a distinct second tap early in the draw cannot become a pending stow intent.
- `:202-218` contains the intended status-driven wait, but the captured session never reached it for these rejected presses.
- The raw `GetAsyncKeyState(VK_TAB) & 1` fallback is not a proven one-press edge. During one held/repeated interval it emitted roughly 60 physical-Tab rejections over 3.8 seconds at keyboard-repeat cadence. It also cannot represent controller/remapped bindings or distinguish a Tab tap from holding Tab for the weapon wheel.

There is **no current holster timeout or retry**. `now` only drives the three-second heartbeat, and `[AlwaysHolster]` contains only `Enabled` and `Log`. A historical 450 ms fallback existed, but it is superseded; the current INI prose saying “shortly after” is stale. When a press was accepted, the log showed task status `8 -> 0 -> 1`, proving the request survived into the task system, not that the animation visibly completed.

### What vanilla actually proves

`act_bankrobbery01.c:10854-10870` defines swap task `716706914` as busy only at status `0` or `1`. Its generic-ped stow helper at `:22028-22061` waits until that task is free, then performs non-immediate hide, selects unarmed without forcing, and calls `TASK_SWAP_WEAPON(..., 0, ...)`. No millisecond pre-stow delay exists.

The closest complete **player-specific** Story path is `act_caunc_rustling_invite.c:6361-6406`. It:

1. disables `INPUT_TOGGLE_HOLSTER` while owning the transition;
2. waits for both swap task `716706914` and perform-sequence task `242628503` to be idle;
3. calls `_HOLSTER_PED_WEAPONS` (`0x94A3C1B804D291EC`);
4. calls `_HIDE_PED_WEAPONS(..., false)`;
5. starts `TASK_SWAP_WEAPON(..., 0, ...)`; and
6. calls `FORCE_PED_AI_AND_ANIMATION_UPDATE` (`0x2208438012482A1A`).

The current mod copied the generic-ped sequence and omits the leading player holster call, the perform-sequence guard, and the final animation update. Those are concrete differences worth a dev-only A/B test, but their undocumented parameters/effect are not yet proven to be the visible root cause.

The authored longarm animation exists in game data: `default.meta:4685-4687` assigns the Carbine Repeater the `...UNARMED@BACK@LONGARMS` swap pair, and `weaponcomponents.meta:4-24` defines the corresponding holster/unholster/strap clips. The game is capable of the requested shoulder-to-back transition; instant attachment is not the only authored behavior.

### Evidence-backed next prototype, if implementation is approved

- Replace the aggregate `IS_CONTROL_ENABLED` ownership decision with explicit named locks: mission, mount, vehicle, prone ownership, binocular ownership, weapon-wheel/frontend state, and any other proven owner. Keep aggregate enabled state as a diagnostic only.
- Recognize one semantic game-action edge (including controller/remaps); do not treat Windows key repeat as multiple presses.
- Distinguish the initial draw press from a separate restow press made while the draw task is active. Latch that second intent once, wait for task `716706914` to leave status `0/1`, then issue once. Do not race a second swap task into the live draw and do not add a guessed delay.
- A/B the current generic sequence against Rockstar's player-specific sequence, logging both task hashes, hand attach points, current weapon, wheel state, explicit lock owners, and `_IS_PED_CURRENT_WEAPON_HOLSTERED` as an unproven traced candidate.
- Acceptance: second taps around 0/100/250/500 ms after draw; idle stow; held-Tab weapon wheel; controller/remap; explicit prone/binocular/mission/mount/vehicle rejection without later phantom firing; rifle/repeater/shotgun/sidearm; one authored visible stow with no teleport or hand/back oscillation.

This was exploratory research only. No code, build, install, label, or issue-state change was performed.

## comment 5550130253 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130253

Created: 2026-08-11T07:13:38Z; updated: 2026-08-11T07:13:38Z

Exact metadata: [source record](sources/comment-5550130253-f321b901f8f57047106f29407516b49020acb7bea0ed1980ce191d699ae50dfc.json).

New evidence resolves the input method.

`marston2.c:62263-62290` disables `INPUT_TOGGLE_HOLSTER` and then reads `IS_DISABLED_CONTROL_JUST_PRESSED` for that same action. This is Rockstar's semantic input path. It supports keyboard remaps and controllers. It does not need `GetAsyncKeyState`.

The current module still reads physical Tab. The earlier log showed repeated events at keyboard-repeat speed. That path should not remain the main input source.

The Aug. 11 log contains only `armed=0` heartbeats. It has no accepted, rejected, deferred, or issued press. It proves that the module ran, but it does not test the holster path.

The next prototype should identify each real lock owner, disable the semantic holster action when the mod owns it, read one disabled-control pressed edge, latch one stow request, wait for swap task `716706914` to leave status 0/1, and issue one player stow sequence. Task status and weapon attach points need readback; the visible animation remains a separate in-game result.

## comment 5550130270 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130270

Created: 2026-08-14T00:02:01Z; updated: 2026-08-14T00:02:01Z

Exact metadata: [source record](sources/comment-5550130270-3cb9f28c56c65bff09bce86ce831f8fb6113b410ef1eae5e1f97d07b4e23c1cf.json).

**Found the post-draw dead window you asked about on Aug 6 — it was lost intent, not a timeout.**

To correct the record first: there is no cooldown, and the earlier claim that the module was rejecting everything was wrong. Your log has 44 `emptyHand` rejections, 8 `controlLocked`, and **2 presses that were accepted and completed a full stow**. So it works sometimes, which is what made it feel random.

The real defect, straight from your log:

```
+1009859ms  gate=emptyHand      <- the draw press
+1010515ms  gate=controlLocked  <- the restow press 656ms later, lost
+1011047..1011312ms  7 more, all lost
```

Four things compounded:

1. **`emptyHand` returned before ownership could exist.** "Put it away while the draw is still playing" had no state to live in, so the press was dropped rather than queued. Three rejections are immediately followed by `armed=1`. That is your dead window.
2. **`controlLocked` was partly the module tripping over its own disable** from the previous tick — a non-deterministic self-lock. That is why tapping Tab many times eventually got through.
3. **Windows key-repeat was being read as real presses** — 8 events in 250 ms is one held key.
4. **The armed test was not Rockstar's** — it checked one hand attach point; Rockstar checks both.

Rewritten: the ownership window is now `armed || swap-task-busy` (so a press during the draw is latched once and issued when the task frees), input is Rockstar's disabled-control edge so remaps and controllers work, the raw key is diagnostic only, and it issues Rockstar's **player** stow sequence — the old code had copied the generic-ped helper, which is a different sequence.

One honest gap: whether that semantic input edge actually fires for this binding in your build is unproven — both accepted presses came via the raw key. There is now a log line that settles it in one session; if it says the semantic edge never fires, the raw key comes back as a debounced fallback.

Test: one press with a rifle in hand should give one authored stow, no teleport-to-back and no hand/back oscillation. Also try a second press *during* the draw.


## comment 5550130282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130282

Created: 2026-08-15T04:45:39Z; updated: 2026-08-15T04:45:39Z

Exact metadata: [source record](sources/comment-5550130282-d7ea1857c045e436258ae50ffc884fae762883b25b18f6570e3dc6aebe4e6bf4.json).

**Tested against your session log rather than asking you again. It was still broken, and the reason is a mistake in the fix I shipped.**

25 Tab presses in your session. **All 25 rejected. Zero accepted, zero issued.** Every rejection is identical:

```
press rejected owner=foreign ctlEnabled0=0 ctlEnabled2=0 selfOwns=0
               pauseMenu=0 binoculars=0 reloading=0 swap=8 perform=8
```

Read that carefully: the action is disabled in both control groups, **we** are not the ones disabling it, **no named owner is asserted** — not the pause menu, not binoculars, not reloading — and both tasks are idle (8 = finished). Nothing was actually holding the control.

**The gate was self-defeating.** I wrote it on the premise that "group 2 is never disabled by this module, so a disabled group 2 proves a foreign owner". Your log disproves that: group 2 is disabled with nothing named. RDR2 disables this action routinely.

Worse, it contradicted the mechanism. This module deliberately reads the **disabled-control** edge (`IS_DISABLED_CONTROL_JUST_PRESSED`) so a press registers *while the action is disabled* — that is the entire design, and it is why the semantic input path was chosen. It then rejected the press **because** the action was disabled. Under that pairing no press could ever be accepted, which is precisely the 25/0/0 the log shows.

**Fix:** rejection is now driven by **named owners only** — pause menu, binoculars, reloading — plus the existing hard gates for mission, vehicle and mount. An unattributed disable is no longer treated as a lock, because it never named anything to begin with. When it does reject, it now logs *which* owner instead of the useless `foreign`.

This also explains the shape of your original complaint. You said Tab worked "maybe 1 in 50 presses" — that is what a gate looks like when it only lets a press through in the rare window where nothing happens to have the control disabled.

Verifier passes. Installed and hash-verified.

Test: draw a rifle and press Tab once. You should get one authored stow, with `press accepted` then `issue stow` then `outcome stowed` in the log. If it rejects, the line now names the owner and that is a different, findable problem.


## comment 5550130293 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/179#issuecomment-5550130293

Created: 2026-08-18T18:13:32Z; updated: 2026-08-18T18:13:32Z

Exact metadata: [source record](sources/comment-5550130293-f8b20ef1929e445d93a8df9c79741d699f74f750c772e7ba6a15ed83afa401e9.json).

**Tab is dead because my last change made this module hold the holster key down forever and then never look at it. That is my fault and it is a straight regression.**

Your 2026-08-18 log settles it without any guessing. The module wrote **88 lines and every single one is a heartbeat** — no press, no rejection, no defer, no stow, nothing. Every heartbeat looks like this:

```
+745281ms INFO [holster] heartbeat armed=1 pending=0 owns=1
     ctlEnabled0=0 ctlEnabled2=0 selfOwns=1
     pauseMenu=0 binoculars=0 reloading=0 swap=8 perform=8
```

Reading that line:

- `armed=1` — rifle in hand, so the feature was live.
- `pauseMenu=0 binoculars=0 reloading=0` — **none of the owner gates I added last time ever fired.** They are not the cause. I want to be clear about that because it was the obvious suspect.
- `selfOwns=1 ctlEnabled0=0` — **the module itself was switching the holster action off, on every frame, for about 400 seconds straight.**
- Zero press lines — and the only input source I left it with never fired once in 745 seconds.

So: I turned the game's own Tab-holster off permanently, and the replacement I put in its place is blind. Vanilla suppressed plus mine blind equals a key that does nothing. Exactly what you got.

**Why it only broke now.** The gate I deleted last time (`control group 2 disabled`) was returning *before* the module ever reached the suppression line. Deleting it was right on its own terms — it genuinely could never let a press through — but it was also the only thing stopping the module from taking the key. Nothing replaced it. That is the regression.

**The input source was never proven and I said so at the time.** Both stows that ever worked came through the raw keyboard read, not the "proper" control edge I switched to. I made the unproven one the *only* way in. That is the underlying mistake.

Three corrections, no new gate added anywhere:

1. **The module no longer silences Tab unless it can actually see Tab.** The suppression only runs after it has observed the key at least once in that session. If it is blind, the game keeps the key and you get vanilla behaviour — the old instant teleport-to-back. Annoying, but never a dead key. That failure mode is gone by construction now.
2. **The keyboard read is a real input again, debounced properly.** The old "key repeat looked like 8 presses" problem was caused by reading the wrong bit — I was reading the bit Windows re-sets on every auto-repeat. It now reads the held state and only counts the moment it goes from up to down, so holding Tab is one press, full stop. The control-based edge is kept alongside it so a controller or a rebound key still works.
3. **Tab is shared with four other actions in RDR2** — weapon wheel, pickup, quick-equip and pistol twirl. I was passing the flag that disables *all* actions on the key, not just the holster. Rockstar passes the other one in all 421 of their own scripts. Fixed. If the wheel or pickup has felt off on Tab lately, that was this.

I also fixed why your log could not answer any of this: the one line that would have said "the key reached us / the key never reached us" was written at a verbosity level that is switched off in a normal launch, so it was thrown away. Every press observation is now written at normal level, and the heartbeat carries running counts of keyboard presses, control-edge presses and suppression frames next to the frame count — so the next log answers it in one line whether or not you turn anything on.

**What to test once this is installed:** draw a rifle and tap Tab once. First tap of a session may still be the old instant stow — that is the deliberate safety behaviour above — and every tap after that should be the proper animated put-away. Then try tapping Tab again *during* the draw, which is the dead window you originally reported.

If it still does nothing, the heartbeat will now say which of the two input sources saw the key, and that is a short, findable problem rather than another round of guessing.

