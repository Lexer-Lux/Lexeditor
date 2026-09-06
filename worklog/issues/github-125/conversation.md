# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356289791 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125

Created: 2026-08-06T02:01:32Z; updated: 2026-09-05T06:56:10Z

Exact metadata: [source record](sources/issue-5356289791-a5a05924ba41d7f93e9c30632e3d94e40ff4ccafb0c96af4d0ed661d801c36f9.json).

In the .ini. Should be disabled by default.

## issue 5356289791 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125

Created: 2026-08-06T02:01:32Z; updated: 2026-09-06T13:07:08Z

Exact metadata: [source record](sources/issue-5356289791-dc8a9bc78c07d3e25dd75237534e7bec8ae8eb960272b39fcdf8274b85151c26.json).

**Status: Idle logging shows no unwanted XP changes; active play still needs checking.** The previously unsafe progress-reset approach must not return.

- [ ] On a spare save, leave Core XP Gain disabled and note your current Health, Stamina and Dead Eye progress. Do ordinary combat/hunting and sustained movement, then compare the same progress displays.
- [ ] Confirm no new progression was earned and existing ranks or maximums were not reduced. Report what changed and attach GameplayTweaks.log from that session.

## comment 5550116204 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125#issuecomment-5550116204

Created: 2026-08-06T02:43:39Z; updated: 2026-08-06T02:43:39Z

Exact metadata: [source record](sources/comment-5550116204-832186143b87a972b3d09701fc6a373298343844f739745ad4c5875b125798b5.json).

Built and installed for testing.

Added `[CoreXPGain] Enabled=0` (disabled by default). When disabled, GameplayTweaks captures the loaded save's existing Health, Stamina, and Dead Eye base ranks and prevents ordinary Rockstar XP awards from increasing them. It does not reset existing levels, alter current core fill/drain, or touch bonus ranks. Set `Enabled=1` for vanilla XP progression.

Build passed with the two pre-existing C4838 warnings. Source/installed ASI and INI hashes match. Needs an in-game check that an activity which normally awards core XP no longer increases the corresponding maximum.

## comment 5550116222 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125#issuecomment-5550116222

Created: 2026-08-13T13:15:27Z; updated: 2026-08-13T13:15:27Z

Exact metadata: [source record](sources/comment-5550116222-aa6e9959690592f1d40d2bf981040266dac20d244190778386b53c50b800a282.json).

just gained xp with the toggle disabled.

## comment 5550116234 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125#issuecomment-5550116234

Created: 2026-08-14T01:19:34Z; updated: 2026-08-14T01:19:34Z

Exact metadata: [source record](sources/comment-5550116234-40bb648efc3ec0ce7cb706083379cb486059534d119d3765fd056762bc7661a0.json).

**You're right, and I know why — but the obvious fix could corrupt your save, so I need one decision from you.**

**What this actually does today.** With the toggle off it holds the *rank* down: it captures your Health/Stamina/Dead Eye base ranks and pushes them back if Rockstar raises one. It never touched the **XP points** that accumulate toward the next rank. So the points keep rising, the award still registers, and you see XP gain — while the level itself is reset behind it. Your report and the code agree.

**Why I have not just clamped the points.** `SET_ATTRIBUTE_POINTS` writes persisted progression, and this project already recorded it destroying exactly that. From `script.cpp:192-195`:

> Feeding CoreClock's ordinary 0..100 fill values to it corrupted the saved maxima on restart (Dead Eye 0, Health/Stamina ~25).

A clamp has to capture a ceiling on some first ready frame. If that read lands before the save's progression is live, it pins your XP at the wrong value **permanently** — and there is no way to distinguish a legitimate 0 from a not-yet-loaded 0, nor any way for me to test it from here. Trading a possible corrupted save to stop a bar filling is not a call I will make for you.

**So this build observes instead of writing.** It captures ranks and points, counts every rise, and logs a heartbeat every 30 s:

```
[core-xp] captured ranks=... points=...
[core-xp] heartbeat enabled=0 rankClamps=N pointRises=N ranks=... points=...
```

There was previously no logging here at all, so "the clamp ran and worked" and "the clamp never ran" were indistinguishable.

**Your choice, once you have looked at that log:**

- **`rankClamps` climbing** → the rank hold is working and you are only seeing XP-bar/notification feedback, with no actual level gain. Possibly good enough, and zero risk.
- **`rankClamps` stays 0 while ranks rise** → the rank hold is broken and that is a straightforward fix with no save risk.
- **You want the XP itself frozen** → say so and I will add the points clamp, with the capture deferred until progression reads as loaded. I would want you to save a backup first, because the failure mode is a corrupted maximum, not a wasted session.

Staying `actionable`.


## comment 5550116246 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125#issuecomment-5550116246

Created: 2026-08-14T05:16:14Z; updated: 2026-08-14T05:16:14Z

Exact metadata: [source record](sources/comment-5550116246-36a6fe28baa829929762a089b1829e651f242f9fe64dd8d7c0c7b047adb9ac70.json).

**The observe-only build I asked you to gather evidence with could not report anything. Fixed.**

Your last session contains **zero** `[core-xp]` lines, while modules dispatched two lines later logged normally. `[CoreXPGain] Enabled=0` on your install, so this module should have been on its active path and writing a heartbeat every 30 seconds.

The cause: both early returns were silent. If the toggle was on, it returned without a word; if the player was not "ready", same. So "the observer never ran", "the toggle was on" and "the player was never ready" were three different situations producing one identical empty log — and the decision I asked you for depends entirely on evidence this build could not produce.

Both paths now emit a heartbeat naming the gate:

```
[core-xp] idle gate=toggle-enabled-vanilla-xp|no-ped|player-not-ready enabled=… ped=… playerReady=…
```

so the next session says which state it is actually in, and the active path's existing `pointRises` counter becomes trustworthy instead of ambiguous.

**Your decision is still the blocker, and my position on it has not changed.** With the toggle off, the rank is held down but the XP *points* still accumulate — which is what you are seeing. Clamping the points means writing persisted progression through `SET_ATTRIBUTE_POINTS`, and this project has already recorded that native destroying saved maxima (Dead Eye 0, Health/Stamina ~25 on restart). A clamp must capture its ceiling on some first ready frame, and a read that lands before the save's progression is live would pin your XP at the wrong value permanently. There is no way to tell a legitimate 0 from a not-yet-loaded 0, and no way for me to test it from here.

So: **hold the rank only** (today's behaviour — the bar fills, the level never rises), or **also clamp the points** and accept a real risk to your progression. I will not choose that for you.

Staying `actionable`. Next session, `pointRises` on the heartbeat tells us whether the points actually climb during normal play, which is worth knowing before you decide.


## comment 5550116258 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/125#issuecomment-5550116258

Created: 2026-08-15T04:48:22Z; updated: 2026-08-15T04:48:22Z

Exact metadata: [source record](sources/comment-5550116258-eab5ca17b61d317b685fd14c67fbe277b995b36cc447f94632691907df8034a1.json).

**The number you needed for the decision is in: the XP points did not rise at all.**

Final heartbeat from your session:

```
[core-xp] heartbeat enabled=0 rankClamps=0 pointRises=0 ranks=7,7,7 points=1100,1100,1100
```

- `enabled=0` — the toggle is off, so the guard is active and holding ranks.
- `ranks=7,7,7` and `points=1100,1100,1100` — unchanged across the whole session.
- **`pointRises=0`** — the observer never once saw the XP points climb.
- `rankClamps=0` — the guard never had to push a rank back either, because nothing tried to raise one.

That is the evidence I said the decision depended on. The case for clamping the points was "they keep accumulating behind the held rank" — and in 31 minutes of play they did not accumulate at all.

**So the risky option looks unnecessary.** Clamping would mean writing persisted progression through `SET_ATTRIBUTE_POINTS`, which this project has already recorded destroying saved maxima (Dead Eye 0, Health/Stamina ~25 on restart). Taking that risk to stop a bar that is not filling would be a bad trade.

**One honest limit:** this is a null result, not a proof. If you did not do much XP-earning activity in that session — combat, hunting, riding hard — then the points had no reason to rise and the observer would read 0 either way. What it does establish is that they do not creep on their own.

If you want certainty before deciding: play a stretch that would normally earn Dead Eye or Stamina XP, then check `pointRises` on the heartbeat. Non-zero means the accumulation is real and we can revisit the clamp with eyes open. Still zero means there is nothing to clamp and this can be closed as working.

Leaving the decision with you rather than picking for you — that is the whole reason this one has stayed open.

