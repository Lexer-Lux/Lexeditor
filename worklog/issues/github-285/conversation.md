# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356329829 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285

Created: 2026-08-15T02:17:22Z; updated: 2026-09-05T07:04:49Z

Exact metadata: [source record](sources/issue-5356329829-5837f5b51725b1191cdc9f055f45931e25e3a46d1cba50413cae4f55bc96082f.json).

<img width="144" height="175" alt="Image" src="https://github.com/user-attachments/assets/3ae140a7-da0c-4520-aecd-dfdb23fb2d20" />

## issue 5356329829 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285

Created: 2026-08-15T02:17:22Z; updated: 2026-09-06T13:32:02Z

Exact metadata: [source record](sources/issue-5356329829-a0ef43245a2545762516d79affa3c3f4f685d3d0c5178abb7c0dec8fdd7c458d.json).

**Closed historical report.** The correction stops intended drain being immediately undone by reserve protection. Its last build note did not confirm installation; current horse-core work remains in #237 and #176.

[Original report image](https://github.com/user-attachments/assets/3ae140a7-da0c-4520-aecd-dfdb23fb2d20).

## comment 5550163183 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285#issuecomment-5550163183

Created: 2026-08-15T03:28:45Z; updated: 2026-08-15T03:28:45Z

Exact metadata: [source record](sources/comment-5550163183-7f9371915e1aabecfd0ff8c3b7cbd90c74041a5b74f7d21680c3576a2ce9f689.json).

**Found it in your log. Two systems were writing the same core, 4 times a second.**

`horse_core_clock` kept its own authoritative value and reconciled it against the game every 250 ms:

```
if (|live - managed| > 1) managed = live;   // adopt big changes
else if (live != managed) write(managed);   // fight small ones
```

Rockstar's background metabolism moves a horse core by **exactly one point**. That is the "small" case, so every nudge was written straight back on the next tick, the engine nudged again, and round it went — a permanent tug-of-war over one value. On the HUD that is a core filling and draining over and over, which is exactly your screenshot.

Your log shows the module running normally the whole time (`executed=1 enabled=1 targets=1`, health/stamina hours 24.0), which is why nothing looked wrong from the module's own point of view — it was doing precisely what it was written to do.

**Why I did not just make our value win harder:** there is no way to stop the engine's metabolism. The only resolved core natives are `_GET_ATTRIBUTE_CORE_VALUE`, `_SET_ATTRIBUTE_CORE_VALUE` and the overpower pair — nothing disables decay. Writing more often would just hide the flicker behind a per-frame fight, which the codex names as a defect in its own right.

**Fix:** the module now adopts engine-side changes of any size and applies the configured drain on top, instead of contesting a value it cannot own. The tug-of-war is gone.

**One honest consequence, because it changes what your settings mean.** The configured drain is no longer a *replacement* for Rockstar's metabolism — it is *additional* to it. Horse cores will fall somewhat faster than `HorseHealthDrainHours` / `HorseStaminaDrainHours` alone suggest. If you want the old "our number is the whole story" behaviour back, that needs a different mechanism than core writes, and it belongs with the drain settings in Lexer-Lux/Lexeditor#237. I have not silently absorbed that.

The heartbeat now reports `adoptedEngineChanges=N`. Under the old code that number *was* the oscillation rate; now a high value just means the engine is active and the module is correctly yielding.

`verify_horse_core_clock_issue_145.py` passes. Built into the development ASI; the install is queued behind the running game.

Test: sit near your horse and watch the core — it should move in one direction only, no visible refill/drain cycling.


## comment 5550163201 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285#issuecomment-5550163201

Created: 2026-08-18T03:43:46Z; updated: 2026-08-18T03:43:46Z

Exact metadata: [source record](sources/comment-5550163201-ac1e72c53553afcfe743215b91ad1debbc2c0241e69dfdbf4e8fc0e5d781622b.json).

Reopening. Lexer, after the time-skip drain started working: *"they're still slowly recovering on their own back up to ~33%"*.

**That is my fix, doing exactly half its job.**

To kill the 4 Hz oscillation I made the module adopt every engine-side change. That was *symmetric* — it accepted Rockstar's regeneration exactly as readily as its drain. Since the engine's metabolism cannot be disabled, unopposed adoption means regeneration always wins and the cores walk back up to whatever baseline the engine wants.

The session log shows how relentless it is:

```
adoptedEngineChanges=0 -> 53 -> 62   (about one minute)
```

~60 engine writes a minute, every one of them adopted.

**Adoption is now asymmetric**, which is the only shape that satisfies both of Lexer's reports at once:

| Observed | Action | Why |
|---|---|---|
| `live < managed` | adopt | engine drained further; additive, wanted |
| `live > managed + 5` | adopt | a real refill — food, tonic, revive |
| `live > managed` (small) | **oppose** | passive regeneration, the thing the feature exists to remove |

The refill cut of 5 is taken from the shipped catalog rather than guessed: the smallest core-restoring consumable in MyOverhaul is 6.25 points (asserted in `verify_core_cost_guard_issue_146.py` alongside MOONSHINE at 50), while passive regeneration moves 1 point at a time. 5 separates them cleanly.

Opposition is tolerance-banded (ignores a 1-2 point wobble) and rate-limited to **once per second**, so it cannot degenerate back into the visible per-frame fight this issue started as.

**The heartbeat was also part of why this took two rounds.** It reported only what the module *did* — never what the cores actually read — so "recovering to ~33%" could not be checked against anything. It now reports engine-read values, not `managedCore`, because a cached value printed as observed state is the same defect class as Lexer-Lux/Lexeditor#236 and Lexer-Lux/Lexeditor#282:

```
regenOpposed=<n> liveCores[health,stamina]=<h>,<s>
```

**Nothing in the verifier guarded Lexer-Lux/Lexeditor#285 at all**, which is how the oscillation could have been reintroduced silently. `verify_horse_core_clock_issue_145.py` now asserts both reports together — adopt decreases, adopt refills, rate-limit opposition, and read live cores — so a fix for either report alone fails the contract. Mutation-tested: reverting adoption to symmetric makes it fail.

Built dev `E4C3FB61F1F2C34FDF98639754AA5796FAA89F42E03E77971A49397A4B824AC1`, installed, hash verified.

**What to check:** cores should now hold where the drain left them instead of creeping back to ~33%, feeding/tonics should still fill normally, and there should be no visible flicker. If it still creeps, `regenOpposed=` in the log says whether opposition fired at all or fired and lost.


## comment 5550163211 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285#issuecomment-5550163211

Created: 2026-08-18T18:04:55Z; updated: 2026-08-18T18:04:55Z

Exact metadata: [source record](sources/comment-5550163211-819276dd472f58f2363b1e2528e593de02a4fa4cef54210f28be2fa0f821526c.json).

**Third round. My last fix caused a new symptom that is the same symptom this issue was opened for.**

Lexer: *"My horse's stamina core is starting to refill for a split second before going back down. Over and over. But not its health core, strangely enough? Could this be the result of the horse drinking feature? But he's not drinking."*

Not the drinking feature. That is the once-a-second regeneration opposition I added this morning, and it recreates the exact fill/drain loop in the original report. **The opposition is withdrawn.** Any correction applied after a visible rise is itself visible, at any cadence, so this could not be fixed by retuning the interval or the tolerance.

His session is unambiguous about what is happening, and it does not match the story I built the fix on:

```
adoptedEngineChanges=0   regenOpposed=48 -> 145 in ~40s
liveCores[health,stamina]=34,26 -> 30,21
"write readback mismatch" lines: 0
```

- `adoptedEngineChanges=0` — the engine **never lowered a core once** all session.
- `regenOpposed` climbing ~2/second — opposition firing continuously on both cores.
- Zero readback mismatches — our writes land exactly, so the rise happens *between* writes, at roughly **+2 points per second**.

And Lexer states that horse health/stamina cores **do not refill at all in vanilla**. If that is right, this is not metabolism — something is writing them. Three of this mod's own modules write horse cores:

| Module | Writes | Notes |
|---|---|---|
| `horse_core_clock.cpp` | cores 0 and 1 | this module |
| `horse_needs.cpp` | core 1 on drink, core 0 on eat | live on the SAME horse (172802) in his log; restore path did not fire |
| `wagon_stamina.cpp` | core 1 only, upward, to a protected floor | draft horses only, floor is 10% |

`wagon_stamina` is the only upward writer and it is core-1-only, which is suggestive given he noticed the stamina core and not health — but it is gated to horses harnessed to a wagon, so it should not have been running. That needs proving, not assuming.

**So the module now adopts upward moves and measures them instead of fighting:**

```
rose=<n> risePoints=<total> maxRise=<largest single jump>
```

That is deliberately a diagnostic, not a fix. It tells us the rate and the largest single jump, which is what separates "a writer doing +2 every second" from "one big restore". I am not adding a fourth control loop before knowing who the writer is.

**Honest consequence:** the creep Lexer reported earlier (cores drifting back up) returns. That is the lesser of the two bugs and not the one this issue is about, and I would rather state that than quietly trade one visible defect for another.

Also corrected while here: `GET_CORE` and `SET_HORSE_CORE` are raw unnamed hashes in script.cpp. They resolve to `_GET_ATTRIBUTE_CORE_VALUE` (`0x36731AC041289BB1`) and `_SET_ATTRIBUTE_CORE_VALUE` (`0xC6258F41D86676E0`) — correctly paired, so the accessors themselves are not the bug.

`verify_horse_core_clock_issue_145.py` now encodes all three rounds and bans the opposition constants by name, so this cannot be reintroduced silently. Mutation-tested.


## comment 5550163228 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/285#issuecomment-5550163228

Created: 2026-08-19T12:14:01Z; updated: 2026-08-19T12:14:01Z

Exact metadata: [source record](sources/comment-5550163228-4ad79f547a9b76e3e1fed3c9de73e950a8ed2f832a8bbf62f125f726c4a66eb6.json).

**Found the writer. It was never Rockstar — it is two of our own features fighting over the same two cores.**

`NoReserveCores` (#78) pins the mount's Stamina core back to `protectedHorseStaminaCore` **every frame** while the outer bar is floored or the horse is swimming (`script.cpp`, the `reserveTick` and `mountStaminaEmpty` branches). The core clock drains that same core on its schedule. Neither can see the other: `protectedHorseStaminaCore` is a **local**, declared at `script.cpp:2009` — long after the module includes at `:1891` — so nothing in `horse_core_clock.cpp` could ever have known about it.

Every detail of Lexer's report is accounted for by that:

| Observation | Explanation |
|---|---|
| `adoptedEngineChanges=0` | correct — the ENGINE never lowered a core. Our own drain did. |
| ~+2 points/second between our writes | the pin, re-applying the protected baseline every frame |
| zero `write readback mismatch` | both writers land exactly; they simply disagree |
| **Stamina but not Health** | the Health pin additionally requires `mountHealth <= floor`; the Stamina pin only needs a floored bar or swimming |
| "refill for a split second before going back down" | drain lowers it, pin restores it, repeat |

His instinct that horse cores do not refill on their own in vanilla was right, and it is what made the mod's own writers the only remaining suspects.

**The fix makes the configured drain authoritative over the protection BASELINE.** Points the clock removes on purpose are subtracted from `protectedHorseStaminaCore` / `protectedHorseHealthCore` before the pins read them, so:

- the pin still blocks Rockstar spending the core as a reserve — Lexer-Lux/Lexeditor#176 is intact, which matters because that behaviour was hard-won across several rounds
- the pin can no longer undo a drain this module performed deliberately

The drop is recorded with the ped handle, because the clock may target an owned horse that is not the current mount, and is cleared every frame so a drop recorded against a different horse cannot accumulate and fire later.

**Contract added and mutation-tested three ways** (clock stops reporting; baselines not adjusted; drops never cleared — all three fail as they should). It also pins the *ordering*: the baseline adjustment must run before the pin reads it, otherwise the pin still restores the drained points for at least one frame.

Built `1E60EBBF1AA91AF0A2C7FB9BEBAA367DC5332CB85160BE63D26803A45A3ACF76`. **Not installed yet** — Lexer is mid-test on `76D3C247` and swapping the .asi underneath him would make his log unattributable.

What to watch once it is in: cores should fall on the configured schedule and stay where the drain leaves them, with no visible refill/drop loop, while a genuinely exhausted horse still cannot spend its core as a reserve. `rose=`/`risePoints=`/`maxRise=` should now sit at or near zero; if they do not, something ELSE is still writing and the counters will say how hard.

