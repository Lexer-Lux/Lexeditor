# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356316170 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237

Created: 2026-08-10T09:42:46Z; updated: 2026-09-05T07:02:08Z

Exact metadata: [source record](sources/issue-5356316170-f55515d3b60c316a803995964989eeabc3a629dc934c5b704235df1c65604308.json).

## Player-facing behavior

Add horse core-drain duration settings alongside the existing Arthur/John core-drain-hour settings. The horse settings must be independently editable and must state clearly which horse core each duration controls.

## Requirements

- Expose horse core-drain hours in the mod settings editor and the in-game settings surface wherever the Arthur/John equivalents appear.
- Preserve independent player and horse values; changing a horse value must not change Arthur/John.
- Use the same units and validation rules as the existing core-drain-hour settings.
- Apply the configured horse values to the owned/current horse at runtime.
- Make restart/hot-reload behavior explicit in the setting help rather than leaving it ambiguous.

## Acceptance test

1. Set visibly different Arthur/John and horse drain-hour values.
2. Confirm the saved INI retains all values independently.
3. Confirm the owned horse drains at the configured horse rates without altering player drain.
4. Confirm editor and in-game settings display the same effective values.

## issue 5356316170 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237

Created: 2026-08-10T09:42:46Z; updated: 2026-09-06T13:17:53Z

Exact metadata: [source record](sources/issue-5356316170-4ac1aeabc903083bf66f1a09d7dad826c1e968d10fe35d87d628ec5af4586e0c.json).

**Status: Recorded closed.** Horse Health/Stamina core durations are separate from player values. The later refill investigation identified the game’s unmounted-horse restore behavior and prepared a prevention fix, but its last note did not confirm installation. Do not infer that result from saved settings alone.

## comment 5550145820 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145820

Created: 2026-08-10T09:54:01Z; updated: 2026-08-10T09:54:01Z

Exact metadata: [source record](sources/comment-5550145820-904c4711dc25a3ffcd144b8fd483100e3d9bddeb48df8ca58d202e9a7e3b63dc.json).

Source implementation is complete and integrated for the next combined build. `[CoreClock]` now has independent `HorseHealthDrainHours` and `HorseStaminaDrainHours` values beside the explicitly Arthur/John-labelled settings. Both editor surfaces use the same hours/0.01 validation, save independently, and hot-reload within about two real seconds with no restart; changes affect future in-game minutes.

Runtime applies the rates to the owned saddle horse and current ridden horse (deduplicated), uses direct horse-core writes with readback, reconciles Rockstar's native one-point metabolism, and preserves substantial food/tonic/script changes rather than undoing them. This remains actionable until the combined ASI is installed and hash-verified, then the independent player/horse drain-rate acceptance test is required.

## comment 5550145842 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145842

Created: 2026-08-10T12:26:46Z; updated: 2026-08-10T12:26:46Z

Exact metadata: [source record](sources/comment-5550145842-72e1ddce6c4bb106386415536e452f67a18242f315180494800b04c2eaca9063.json).

i was on my horse and at least one of its bars drained when i set the time to night. then i wasn't on my horse but i could still see its cores. and changing the time reduced my cores, but not my horse's.
come on...

## comment 5550145861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145861

Created: 2026-08-11T04:06:06Z; updated: 2026-08-11T04:06:06Z

Exact metadata: [source record](sources/comment-5550145861-231ad8cffd382815a985cf6bbe165802b9559ddb78ec8b5b4c8c7ddbc077cd8f.json).

Did nothing. What does the log say?

## comment 5550145883 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145883

Created: 2026-08-13T06:57:51Z; updated: 2026-08-13T06:57:51Z

Exact metadata: [source record](sources/comment-5550145883-69769f13bde918fbc6986bddedde7084857cf15976cc34af1158ef14b8999ce4.json).

still absolutely nothing. this is getting ridiculous.
if i have horse cores displayed, then find the horse behind them and decrease their cores over time.
surely it can't be that hard?

## comment 5550145897 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145897

Created: 2026-08-14T00:48:26Z; updated: 2026-08-14T00:48:26Z

Exact metadata: [source record](sources/comment-5550145897-bb4ff6060deea53daf8c0bb0b03d7450a1a9d144949cee9042c757409f084477.json).

**Found it. It was never a drain bug — the module could not find your horse.**

Your exact words were "find the horse behind them and decrease their cores over time", and that turns out to be precisely the missing step.

Every one of the 59 core-clock heartbeats in your session reads:

```
[horse-core-clock] heartbeat executed=1 enabled=1 targets=0 owned=0 current=0
```

`executed=1 enabled=1` — the module ran flawlessly, every tick, for the whole session. `targets=0` — it had nothing to drain. The drain code was fine and never got a horse to apply it to.

**And the horse was never actually missing.** In the very same build, `horse_needs` resolved it on every single heartbeat, and its candidate breakdown names the failure exactly:

```
horse=278788 horse-source=active_horse
candidates[mount,led,active,saddle,owned] = 0,0,278788,278788,0
```

Five ways to find your horse. `active` and `saddle` both hold it. `mount` and `owned` read 0 — and those two were the **only** ones the core clock consulted. `mount` is 0 because you were on foot, and `owned` was 0 the entire session. So it asked the two questions guaranteed to come back empty while a sibling module three files away had the answer the whole time.

Fixed by giving it that module's resolver instead of its own weaker lookup, so there is now one source of truth: if horse needs can see your horse, the core clock can too. Its heartbeat also reports the resolution source and all five raw candidates now, so a future `targets=0` says *which* lookup failed rather than only that nothing was found — that ambiguity is what made this read like a drain bug for so long.

One integration detail, since it explains a change outside the module: the resolver lives in `horse_needs.cpp`, which was included *after* `horse_core_clock.cpp`, so the include order had to swap. Nothing else uses the core clock's symbols and the dispatcher call is unchanged.

Built, installed, hash-verified.

**Test:** leave the horse alone and let time pass — cores should now fall at the configured `HealthDrainHours`/`StaminaDrainHours` (both 24.000 on your install). The heartbeat should read `targets=1` with `horse-source=active_horse` or `saddle_horse` instead of `targets=0`. Sleeping or riding to advance the clock is the quickest way to see it move.

Not runtime-verified — no frame has run it. But `targets=0` had a proven cause and this removes it.


## comment 5550145912 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145912

Created: 2026-08-15T20:22:57Z; updated: 2026-08-15T20:22:57Z

Exact metadata: [source record](sources/comment-5550145912-8d2b0650795b87d5d643b16fdcbcb3770549df8dc165d7250cb3e0e0c21d606f.json).

<img width="251" height="189" alt="Image" src="https://github.com/user-attachments/assets/10913fea-2033-4f74-84ff-d10bed86318c" />

it's working now! however, i'm noticing that once their cores drain they start...refilling on their own? they've refilled all the way to like 33% in a few seconds. which kinda defeats the entire purpose of the mechanic..

## comment 5550145931 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145931

Created: 2026-08-20T05:57:33Z; updated: 2026-08-20T05:57:33Z

Exact metadata: [source record](sources/comment-5550145931-61c5c8ca4577526324cffbb7ee2c770518f39601a190f5b0f371fe4b90036060.json).

**The settings are reaching your horse. The log just could not show it — so I made it show it, and it turned up something you should decide on.**

Your latest session log, 34 core-clock heartbeats over 39 minutes:

- The horse is found every single time now: `targets=1 horse-source=active_horse`. The old `targets=0` problem is gone for good.
- Your settings are live: `healthHours=24.000 staminaHours=24.000`, straight from the INI.
- **But the cores sat at 30,30 the whole 39 minutes.** One dip to 29, then straight back to 30.

Here is why nobody could tell you what was going on. The log printed `jumpMinutes`, which sounds like "minutes charged" but is actually a single snapshot of the last quarter-second — and the in-game minute only ticks over on about one snapshot in eight. So 32 of the 34 lines read `jumpMinutes=0`, and there was no running total of anything. That means "the drain setting never touched your horse" and "the drain setting touched your horse and something put the points straight back" wrote **exactly the same log**. No amount of reading it could tell them apart. That is the real reason this issue kept going in circles.

**What I changed:** the heartbeat now carries running totals instead of a snapshot — how many in-game minutes were actually charged, how many points the setting actually removed, how many points your configured hours *say* should have been removed, the leftover fraction, and the core values from when the session started. Those are counters only; nothing new writes to a core, so the fill/drain fix from the other issue is untouched.

**What that already tells us, and it is worth your attention.** You were on foot for that entire session — `current=0` on all 34 lines — and the cores still crept upward 26 times. That rules out all three of the mod's own horse-core writers, because none of them can run while you are unmounted: the reserve-core pin only runs when you are on the horse, the wagon code only when you are driving a wagon, and horse feeding/drinking only during an actual eat or drink (it logged `action=0` all session, no restores at all).

So something outside this mod is putting roughly one point back at about the rate a 24-hour drain takes one out. **They cancel.** That is why your cores park at 30 and never move.

That leaves a genuine fork I do not want to pick for you:

1. Find and stop whatever is restoring the points, or
2. Have the mod push the core back down right after it rises — which is exactly the "refill for a split second then drop, over and over" flicker you already told me to stop doing.

I am not doing (2) behind your back. Tell me which you want.

**Not built or installed yet** — this is source only, so nothing has run a single frame of it. Once it is in, the check is one line: leave the horse alone for a few minutes and look at a heartbeat. If `drainedPoints` and `expectedPoints` roughly match while `liveCores` has not fallen, the settings work and the restore is the whole problem. If they disagree, the setting is not reaching the horse and that is a different bug.


## comment 5550145947 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145947

Created: 2026-08-20T06:48:25Z; updated: 2026-08-20T06:48:25Z

Exact metadata: [source record](sources/comment-5550145947-77ff39675b8d77a35462cc61260aba1ab9f3a2e3903e2f6a1cd1e79306800be2.json).

let's do 1 if at all possible. okay, i had the game paused in the background for a while but i set the horse's drain times to 1 hour and set the time forward in rampage editor. all 5 cores drained, as usual. the horse's cores went back up to ~33% or so, but it seems almost like they were slower?

## comment 5550145958 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/237#issuecomment-5550145958

Created: 2026-08-20T07:38:02Z; updated: 2026-08-20T07:38:02Z

Exact metadata: [source record](sources/comment-5550145958-d5b565f4377986daf8b266e62cba7ce0e5b9e95c68d71eefd2888e5e8a1e10e0.json).

The refill is now identified. Current 1491.50 `player_horse` restores an unmounted owned horse to 30 core points in one-point steps. That matches your report and the fresh log.

The repair uses Rockstar's own horse-record flag 128 before that restore can run. It does not raise or correct a core afterward, and it releases only the flag instance it acquired. The development build completed, but I did not install it.

Test with the one-hour setting: leave both horse cores below 30 while dismounted. They must stay below 30 and keep falling; food, tonic, revive, and mission behavior must still work.
