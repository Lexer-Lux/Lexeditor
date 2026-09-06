# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356323028 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261

Created: 2026-08-11T01:23:13Z; updated: 2026-09-05T07:03:31Z

Exact metadata: [source record](sources/issue-5356323028-8ec012826a748f3d1366a61c1c2bd73f21ee45ba4863619665cfc37a05bbe3da.json).

Started sliding. And then when I stopped, I got teleported and put into climb mode on...uh, nothing.

## issue 5356323028 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261

Created: 2026-08-11T01:23:13Z; updated: 2026-09-06T12:56:53Z

Exact metadata: [source record](sources/issue-5356323028-71a1363ae7539e5b6eba8a74e82aeab85fe67b0e74ea3e7aba296b3ed26fb3c7.json).

Prevent repeated falling/snap-back loops, underground climbing and anchors in empty space. Unsafe surfaces must release safely rather than pretend to fit.

**Status: Latest combined surface/state repair is source-only.** It has not been built or installed. Deliver and verify it before repeating slide-to-climb or angled-surface tests.

## comment 5550153890 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550153890

Created: 2026-08-11T01:24:43Z; updated: 2026-08-11T01:24:43Z

Exact metadata: [source record](sources/comment-5550153890-74bdab659d83e001da4dc365079ecf8fab4246a939cdd2596f2d61e99b3bcb24.json).

I'm sticking straight up. Which means the entire "rotate and position the player based around their hand/footholds so they'll always be touching the surface" -- something I asked you to do form the beginning -- is a total lie and you never did it? Or what else could explain this?

## comment 5550153926 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550153926

Created: 2026-08-11T04:47:16Z; updated: 2026-08-11T04:47:16Z

Exact metadata: [source record](sources/comment-5550153926-3c146cecb845a42a002f29d3544d3bac1581418610e8c3b394335f45b1d1f825.json).

Sliding still exists.

## comment 5550153964 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550153964

Created: 2026-08-11T09:34:27Z; updated: 2026-08-11T09:34:27Z

Exact metadata: [source record](sources/comment-5550153964-d93284502df21814f5c7e1a79c67f26009ef299c6a69ddcccea6275e39bd0b23.json).

The phantom-climb takeover is repaired, but that does not remove sliding itself. The later trace showed downhill sliding while Rockstar's own sliding predicate was false, so the existing conversion hook cannot catch it. Story and the SDK expose only a read-only sliding predicate and mission-specific blocking volumes; there is no resolved global slide-disable control. Removing every slide would require a continuous velocity, coordinate, or task fight, which I will not ship after those paths already caused movement failures. I am marking the full no-sliding request unfeasible rather than pretending the partial repair satisfies it.

## comment 5550154002 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154002

Created: 2026-08-13T01:42:11Z; updated: 2026-08-13T01:42:11Z

Exact metadata: [source record](sources/comment-5550154002-49c3a6c60d3786e729f34356fa77cbe580452cdcbc593c2fa1316408fd7a6f4a.json).

I'm not asking for a disable slide control? And I thought you already got close before? Can you not find what causes sliding -- like what angle threshold or circumstances cause it and immediately push him into climb mode before that happens?
Worst case scenario is we detect the sliding state and have him quickly do an anim transition into climbing so it looks like he's catching himself. Surely there must at least be a way to detect sliding mode? Surely?

## comment 5550154044 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154044

Created: 2026-08-14T00:38:57Z; updated: 2026-08-14T00:38:57Z

Exact metadata: [source record](sources/comment-5550154044-713e9f8158e190ea175f726600080cc31fd96a5aacd406ef6138f1a8d5875a69.json).

**Answering your question directly — and the answer ties this issue to the climbing bug I fixed today.**

**"What angle threshold causes it?"** RDR2 does not expose one. Its slide state is `PED::_IS_PED_SLIDING` (`0xD6740E14E4CEFC0B`), a read-only flag; there is no native for the engine's slope threshold and no setter. So the engine's own number cannot be read or changed — which is why nobody has been able to hand you one.

**"Can you push him into climb mode before that happens?"** That is exactly what the code already tries to do, and yes it is the right approach. There is a pre-slide path — `losingFooting` — which fires when you are pushing into a sloped face but being carried backwards, *before* Rockstar owns the slide. The mod's own threshold is `[Climbing] MinimumSurfaceAngleDegrees`, currently **45°** (clamped 35–88), converted to a surface-normal test.

**So why has it never worked?** Because that whole path was unreachable. The chain is:

```
losingFooting  needs  slopedContact
slopedContact  needs  contactFresh
contactFresh   needs  a verified surface from the probe rays
```

And today's Lexer-Lux/Lexeditor#193 finding is that **the probe rays were being fired about a metre too high.** The ped's entity root is not at his feet — `GET_ENTITY_HEIGHT_ABOVE_GROUND` read 0.99–1.01 on all 620 grounded samples of your session — so every ray went out at chest-to-overhead height and found nothing. The scan hit a wall 14 times in 787 lines.

Your log then reads exactly as that predicts: `nativeSlide=0 losingFooting=0` on **every single sample**. The pre-slide detection you are asking for never got the chance to fire once. It was not tuned wrong; it was starved of input.

The ray heights are now anchored to the measured ground under the ped (measured per batch, not assumed, and ignored outside a plausible 0.20–1.50 m range). That is installed. It does not guarantee this issue is fixed, but it removes the reason the pre-emption could never trigger.

**If it still slides after that**, the tuning lever is `MinimumSurfaceAngleDegrees`: lower it (towards 35) to make the mod claim shallower scree slopes as climbable and pre-empt earlier. It hot-reloads, so you can sweep it in-game without a restart. I have not changed it from 45, because moving a threshold that has never once been reached would be tuning blind.

Staying `actionable` — nothing here is proven in game, and your "worst case" fallback is still on the table if pre-emption proves unreliable.


## comment 5550154082 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154082

Created: 2026-08-14T05:54:47Z; updated: 2026-08-14T05:54:47Z

Exact metadata: [source record](sources/comment-5550154082-ab92a8d3a36c996323f9c65ff2d48603b9f84b488ce29b19b8f3f4f93b48cb64.json).

**The blocker this issue named is now fixed and installed — so this is worth retesting, together with Lexer-Lux/Lexeditor#193.**

The chain diagnosed here was:

```
losingFooting needs slopedContact needs contactFresh needs a verified surface
```

and no verified surface was ever produced, so the pre-slide path could never run.

Today I found why, under Lexer-Lux/Lexeditor#193: `GET_ENTITY_HEIGHT_ABOVE_GROUND` reads ~1.0 on every grounded frame — the ped's origin sits about a metre above his feet, so every probe ray was fired a metre too high, chest to overhead. The scan found a surface 14 times in 787 lines. The probe heights are now measured against the ground beneath him each batch rather than assumed, and that is installed.

If that was the whole story, `contactFresh` starts producing surfaces, `slopedContact` becomes reachable, and the `losingFooting` pre-slide grab at `[Climbing] MinimumSurfaceAngleDegrees` (currently 45°) can finally fire before Rockstar owns the slide.

I am **not** claiming that fixes sliding. Nothing was written specifically for this issue, and the chain being unblocked in principle is not the same as it working. Staying `actionable`.

Worth knowing for the test: the engine's own slide threshold still cannot be read or changed — `_IS_PED_SLIDING` is a read-only flag with no setter — so the mod can only get in first, never raise Rockstar's bar.

Test it in the same session as Lexer-Lux/Lexeditor#193: walk into a slope steep enough to slide on. Either he grabs it before the slide starts, or the log's `manual grab abandoned reason=` names what refused it this time. And your original report here — sliding, then being teleported into climb mode on nothing — should be checked too, since "climb on nothing" was the same missing-surface bug.


## comment 5550154122 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154122

Created: 2026-08-15T02:18:07Z; updated: 2026-08-15T02:18:07Z

Exact metadata: [source record](sources/comment-5550154122-05e8f8452d0d744f9283107127f481361a45059864c022d0be1993ce1fce3f19.json).

He slides for a bit, but like...not in the sliding position. While standing. And his movements are big jumps, not continuous. And after a bit of that, THEN he goes into climb mode.

## comment 5550154154 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154154

Created: 2026-08-20T07:16:25Z; updated: 2026-08-20T07:16:25Z

Exact metadata: [source record](sources/comment-5550154154-24642ed827d2cb50cebb45daf44d81617d2dd4bee4ef1f57dca4e97ee16385e5.json).

I see no difference.

There should be 3 ways of entering the jump state:
1. Pressing jump while a forward input is also inputted
2. From a slide
3. Reverse ledge grab.

In both 1 and 2, you need to make John/Arthur do the vanilla jump animation that transitions into the climbing animation, and make his momentum move him into the perfect position + rotation to be touching the wall (plus a little bit of upwards movement, like 2ft). Then he's in the climbing state.

For Lexer-Lux/Lexeditor#101: this should only be doable when standing or crouched but not prone.
For Lexer-Lux/Lexeditor#102: you need to detect if he's sliding and IMMEDIATELY halt his fall and do the jump into climb thing. Preferably before the end of the frame so the player never sees him start sliding for a split second before jumping into this climb mode.
Lexer-Lux/Lexeditor#103 isn't part of this issue so DW abt it here.

Is this doable? If so, do it.

## comment 5550154190 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154190

Created: 2026-08-20T08:28:52Z; updated: 2026-08-20T08:28:52Z

Exact metadata: [source record](sources/comment-5550154190-a416c61524ca877d6469fbf6e1fcd1445d67bca6816d9d3f3c7fe0741afaa8f3.json).

Yes. I implemented the standing/crouched forward+jump path and the prequalified slide path. Prone is excluded, and reverse ledge grab stays separate.

Both paths now start Rockstar's jump task, add one directed push with about 0.61 m of rise, and enter climbing only after the game reports a real jump, the climb animation is loaded and accepted, and the wall target is within 0.45 m. A refused jump or entry animation releases control instead of pulling the player by coordinates. Dodge roll and climbing also cannot consume the same Space press or queue a delayed roll from it.

One engine limit remains: the native sliding flag is read-only. The mod can intercept a proved steep-surface transition before the visible slide, but it cannot cancel an unknown slide threshold inside Rockstar's code.

After the next install, test forward+Space while standing and crouched, confirm prone does not enter, and walk into a steep proved surface. Each accepted case must show one normal jump into the climb animation with no standing slide, large coordinate steps, delayed teleport, or double stamina charge.

## comment 5550154218 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154218

Created: 2026-08-20T12:53:14Z; updated: 2026-08-20T12:53:14Z

Exact metadata: [source record](sources/comment-5550154218-0086e636a77d9b080359d25187b2e33c54d54dd3446450364ded62d9954ba4b7.json).

Returned test disproves the current repair. Starting the climb from slide can enter a repeated fall and snap-back loop, then freefall, then climb. Downward climbing can pass below terrain. Surface fitting still does not rotate and place Arthur against angled or irregular geometry, so he can anchor in empty space. The ledge-top state also has no proper terminal condition and permits upward climbing into empty space. This is actionable as one surface-fit and state-transition failure, not as isolated animation tweaks.

## comment 5550154242 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/261#issuecomment-5550154242

Created: 2026-08-20T14:03:43Z; updated: 2026-08-20T14:03:43Z

Exact metadata: [source record](sources/comment-5550154242-076495c02a48fc8be9c0251334dbfb36ac975d6378a7d248b54ffaf5b588d940.json).

The repeated fall/teleport loop came from a climb target below Arthur's live root while the entry impulse still forced him upward. The old floor check also used an impossible root-height threshold, the top-out test treated a foot probe as the head, and weak aggregate support allowed empty-space anchors. Source now solves from the live root and contact plane, requires upper and lower support, blocks underground/unsupported movement before writing coordinates, and hands only a proved landing to vanilla climb. Unsafe angled alignment now releases instead of pretending it is fitted. The focused contract passes 67 guards and rejects 27 regressions. This has not been built or installed, so Lexer-Lux/Lexeditor#261 stays actionable.
