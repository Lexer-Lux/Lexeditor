# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356320209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252

Created: 2026-08-10T15:30:11Z; updated: 2026-09-05T07:03:03Z

Exact metadata: [source record](sources/issue-5356320209-30e98113b79713647f18f210d66d7c410a772eef8fbea7cd4bfe2df9a9486868.json).

Climbed onto a house with an angled roof, about 45deg. When I got to the top instead of mantling I left climb mode. Fell to the ground. Then got teleported onto the roof??????????

## issue 5356320209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252

Created: 2026-08-10T15:30:11Z; updated: 2026-09-06T12:56:41Z

Exact metadata: [source record](sources/issue-5356320209-159087f87e6d1a5ba827d8240228138427206fbfceb75c9e95406ea98ccba399.json).

Climbing onto an angled roof should produce a real mantle or retain a safe grip, never a fall followed by teleporting back up.

**Status: Unresolved.** A timeout only bounded the stuck state; it did not fix the fall/snap itself. Current climbing-entry failures also block useful testing. Repair the traversal path before another roof test.

## issue 5356320209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252

Created: 2026-08-10T15:30:11Z; updated: 2026-09-06T12:56:41Z

Exact metadata: [source record](sources/issue-5356320209-d5cc91be0cc4b09ca8adc224179d1af77ddc5956c34404ccd6958654c9c36970.json).

Climbing onto an angled roof should produce a real mantle or retain a safe grip, never a fall followed by teleporting back up.

**Status: Unresolved.** A timeout only bounded the stuck state; it did not fix the fall/snap itself. Current climbing-entry failures also block useful testing. Repair the traversal path before another roof test.

## comment 5550150683 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252#issuecomment-5550150683

Created: 2026-08-10T17:20:50Z; updated: 2026-08-10T17:20:50Z

Exact metadata: [source record](sources/comment-5550150683-959499470692c73770459f8aaae9aefd38c3364916075c6657f1c67ecccb9da9.json).

The angled-surface mantle repair is installed. The old code released the wall before TASK_CLIMB was accepted, then teleported to the cached roof target 1.2 seconds later—the exact fall-then-roof-snap you reported. This build keeps the verified lip until Rockstar reports the climb/vault task accepted, never performs that delayed coordinate snap, and returns to attached climbing on rejection. Test a flat lip and roughly 45-degree roof; rejection may remain attached, but it must not release/fall and later teleport.

## comment 5550150699 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252#issuecomment-5550150699

Created: 2026-08-11T01:09:07Z; updated: 2026-08-11T01:09:07Z

Exact metadata: [source record](sources/comment-5550150699-86a3b0ffa5f8642b24f780e7b6ed91abe78323d023d7c1a093e0d18773815955.json).

Now he like....kept climbing. His hands grabbed on to the open air, which should never happen. 
THEN he fell.
What do the logs say?

## comment 5550150718 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252#issuecomment-5550150718

Created: 2026-08-11T01:46:03Z; updated: 2026-08-11T01:46:03Z

Exact metadata: [source record](sources/comment-5550150718-4602dcb38cbf95419d09b0150546aeb18f1edd590f131dc80d7ca79c9d2791df.json).

The mantle task completed without a visible native traversal, then held Up moved the retained anchor into open air. After that rejection, climb movement is now frozen until Up is released. The result must be either a real mantle or continued attachment at the lip, never a fall followed by a delayed snap.

## comment 5550150733 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/252#issuecomment-5550150733

Created: 2026-08-14T06:15:05Z; updated: 2026-08-14T06:15:05Z

Exact metadata: [source record](sources/comment-5550150733-d7d088c5d3ec1be50eff342425ab5fa98d9de68e02cb7711aa4a3ab336efada3.json).

**The freeze was deliberate, but it had no way out other than you letting go.**

"Climb movement is now frozen until Up is released" is the retained-lip block doing what it was written to do: after a rejected native top-out, the lip is kept and Up is ignored so a held stick cannot walk the retained anchor straight back into open air. That part is intentional.

What was not intentional is that **releasing Up was its only exit, with no bound**. Holding Up because you are trying to climb — the obvious reaction to being stuck — keeps it latched indefinitely. A latch with one input-shaped exit and no timeout is a stall waiting to happen.

It now also expires on its own after 2 seconds. Releasing Up still clears it instantly; the timeout only bounds the worst case, and when it fires it says so:

```
[climbing] top-out block expired without release moveY=… heldMs=…
```

**On the rest of your requirement** — "either a real mantle or continued attachment at the lip, never a fall followed by a delayed snap" — I have not fixed that, and I am not going to guess at it. But I have made it measurable. The suspicious step is that this path calls `CLEAR_PED_TASKS` while physics is owned, which is the most plausible way you end up falling, and then re-anchors, which would read as the snap. The rejection line now records the ped's actual state at that exact moment:

```
native top-out rejected; retained lip taskStatus=… falling=… heightAboveGround=… blockedUntilRelease=1
```

- `falling=1` with a rising `heightAboveGround` → he genuinely leaves the wall at the clear, and the fix is to stop clearing tasks while physics is owned.
- `falling=0` and the height steady → he stays on the lip and the visible problem is the animation stalling, which is a completely different repair.

Those two need opposite fixes, which is why nobody should pick one blind.

Also relevant: today's Lexer-Lux/Lexeditor#193 fix corrects probe ray heights that were being fired about a metre too high, and mantling depends on those probes finding the lip — so this path may behave differently now regardless.

Moving to `test me`. Mantle onto an angled surface a few times while holding Up, and see whether you still get frozen and for how long.

