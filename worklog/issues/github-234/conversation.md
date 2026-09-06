# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356315482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/234

Created: 2026-08-10T06:05:18Z; updated: 2026-09-05T07:01:58Z

Exact metadata: [source record](sources/issue-5356315482-2be52b9f00cb65d0f03928c800b7583c4b7961ccdb0fd2ce86188ee5cf7f0d86.json).

(No body was present in this captured version.)

## issue 5356315482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/234

Created: 2026-08-10T06:05:18Z; updated: 2026-09-06T13:29:24Z

Exact metadata: [source record](sources/issue-5356315482-0585b980cb80e7bf9cb34552ba7f9c9b6e24d0a691b79d9977c21762489cea8f.json).

I think the human side is done, I need to understand the horse movement so I can do theirs.

## issue 5356315482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/234

Created: 2026-08-10T06:05:18Z; updated: 2026-09-06T13:29:24Z

Exact metadata: [source record](sources/issue-5356315482-e0fcb53f0bdb0c0f51b9af65a15644d3d5740010ccb57d2a46ce8ce4fd522638.json).

I think the human side is done, I need to understand the horse movement so I can do theirs.

## issue 5356315482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/234

Created: 2026-08-10T06:05:18Z; updated: 2026-09-06T18:48:01Z

Exact metadata: [source record](sources/issue-5356315482-5b0df31c9207d398c096ed3057d668554caac5b5e9adf22af531d8f98fbde689.json).

You believe the human movement work is done and want to understand horse movement before designing its rework.

**Actionable: research and explain the horse gaits, input transitions, speed controls and relevant limits.** Do not ask you for the horse design before supplying that explanation; human-side acceptance has not been independently verified here.

## issue 5356315482 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/234

Created: 2026-08-10T06:05:18Z; updated: 2026-09-06T18:48:01Z

Exact metadata: [source record](sources/issue-5356315482-df018fafc17874243f8aa00947ad5ceb6b5318a7373b067067406111f7d48a31.json).

## How horse movement actually behaves

The useful mental model is **a latched requested gait/speed plus a separate full-gallop/sprint request**, not “hold the stick farther = proportional speed” and not the same walk/run/sprint switch used on foot.

### Player input

On controller, steering comes from the left stick. Repeated taps of the horse accelerate button (`A`/`X`) raise the horse's requested pace through progressively faster locomotion states; tapping the brake (`RB`/`R1`) steps it back down. Holding the brake brings the horse to a stop. Holding/tapping acceleration aggressively requests the fastest gallop rather than merely another ordinary cruise step. Keyboard maps the same idea to movement plus Sprint/Slow Horse (`Shift`/`Ctrl` by default).

This is why a horse can keep a moderate pace without the player continuously supplying a proportional analogue throttle. Community descriptions disagree on names/counts for the intermediate animation states—people call them walk/trot/canter/jog/run differently—but consistently observe multiple persistent speed steps between walk and maximum gallop. The labels are less important than the state-machine behavior.

At high gallop, rhythmic acceleration input is special: timing taps to the stride reduces stamina cost compared with simply forcing maximum pace. Holding the accelerate input is effectively the easy “go flat out” command and burns horse stamina. Companion/formation riding also has separate speed-matching behavior, so it must not be mistaken for ordinary free-roam gait selection.

### What determines the speed you actually get

The requested gait is only one layer. Actual movement is then constrained by the horse/engine state: the horse's authored speed/acceleration characteristics, current stamina, terrain and slope, path/obstacle avoidance, turning, fear/agitation, rider/mission state, settlements/camp restrictions, formation/cinematic tasks and other engine-owned locomotion rules. Bonding additionally unlocks handling maneuvers and stamina-management benefits; it should not be modelled as merely another raw top-speed multiplier.

RDR2 exposes generic ped movement natives such as `SET_PED_MAX_MOVE_BLEND_RATIO`, but the public NativeDB does **not** document that as “horse gait N.” Using a raw blend or velocity cap as the whole horse rework risks exactly the wrong result: animation/hoof cadence, pathing and requested gait can disagree with physical travel speed.

### What this means for our rework

The clean design surface should treat these separately:

1. **Cruising gait selection:** what each accelerate/decelerate tap selects and whether the selected pace latches.
2. **Maximum gallop/sprint:** the separate stamina-consuming top-speed request and its tap/hold behavior.
3. **Stamina economics:** drain at fast gaits, rhythmic-tap efficiency, recovery and exhaustion limits.
4. **Horse performance:** authored speed/acceleration differences and any overhaul multiplier, without using it to redefine the input state machine.
5. **Handling/context:** turning, braking, obstacles, terrain, towns/camps, formation/cinematic riding and fear states should remain engine-owned unless a specific problem calls for changing them.

So if the goal is to make horse movement mirror the simplified human controls, the safest proposal is **not** “force a movement blend ratio every frame.” It is to intercept the player's requested pace: e.g. ordinary forward movement chooses the agreed cruise gait, Hold Sprint requests the top gallop, release returns to cruise, and Slow/Brake still steps down/stops. Then tune stamina and maximum-performance separately.

### Confidence / remaining measurement

The input/gait behavior above is observable vanilla behavior and is consistent across current player-control references. Exact internal thresholds, blend ratios and authored gait names are not exposed by the public NativeDB, so those numbers should be measured with a small runtime speed/gait trace before implementing a rework rather than invented from community labels.

This issue asked for the horse-movement explanation **before** designing the rework. That research deliverable is complete; no horse-control gameplay change is claimed here.
