# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356321861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257

Created: 2026-08-10T18:25:13Z; updated: 2026-09-05T07:03:19Z

Exact metadata: [source record](sources/issue-5356321861-7af099f21af72003c456cd5de6fab3c893e055f641c7e7c33eba19ce77de899a.json).

Hard to explain but there's occaisional hitching and stuttering when climbing.

## issue 5356321861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257

Created: 2026-08-10T18:25:13Z; updated: 2026-09-06T13:18:17Z

Exact metadata: [source record](sources/issue-5356321861-4444ee54f18b3508cf77228b65aeed349e9553df93a0cdef8482632f37b38f79.json).

**Status: Closed historical report; no final pose-flicker repair is documented here.** The last user report changed the symptom from jitter to repeated brief wrong poses. Current climbing entry, animation and surface failures remain in #193, #251 and #253; telemetry alone was not a fix.

## comment 5550152301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257#issuecomment-5550152301

Created: 2026-08-10T23:45:53Z; updated: 2026-08-10T23:45:53Z

Exact metadata: [source record](sources/comment-5550152301-33cea5f3d67338db421b2c71aff81965b56b260c313d3d735aa12fbeae0f5896.json).

Installed the climbing continuity correction. The authored start-to-loop transition no longer resets movement gain to zero 240 ms into the same held direction. Test sustained up/down climbing and direction changes for any hitch or stop.

## comment 5550152309 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257#issuecomment-5550152309

Created: 2026-08-11T01:59:05Z; updated: 2026-08-11T01:59:05Z

Exact metadata: [source record](sources/comment-5550152309-2d0027c7d3e9f66fdd5064e32cf9fa719c157e8c34d20f1e6c2410bc5d99a5f5.json).

Still there. What does the log say? Can you see the jittering in there?

## comment 5550152326 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257#issuecomment-5550152326

Created: 2026-08-13T01:43:17Z; updated: 2026-08-13T01:43:17Z

Exact metadata: [source record](sources/comment-5550152326-d54b10a771dc841e8f901113d21e08358c740f4aa86595d5b0ce3223a45f41d1.json).

it almost feels worse than before.

## comment 5550152336 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257#issuecomment-5550152336

Created: 2026-08-14T06:17:58Z; updated: 2026-08-14T06:17:58Z

Exact metadata: [source record](sources/comment-5550152336-052c830e873ded37b43cdce5390633130ee1a6d1fc41ccc62ffdf4202d5d0f5a.json).

**This issue has never had a single number behind it. Now it will.**

Everything here has been "occasional hitching" and "almost feels worse than before" — real reports, but nothing measurable, so every pass has been someone's guess about which of several plausible causes it was. There is no jitter telemetry in the build at all today.

**The leading hypothesis, and why "worse than before" fits it.** While attached, the climb root is corrected outward whenever your hands would cross behind the surface. That clearance is sampled from **live animated bone positions, every frame**. Under Lexer-Lux/Lexeditor#193 I proved those hands swing far enough off the wall that probes lose contact completely at high animation phase — contacts read 4–6 hits early in a clip and **0** through the middle of it. If the clearance oscillates with the animation, the correction pulses in and out at animation frequency, and the root gets nudged repeatedly. That is what hitching looks like. It also explains "worse": bone-anchored contacts made the coupling to animation stronger than the old fixed heights.

**I have not applied that as a fix.** It is a good hypothesis and it is not proven, and this issue does not need another confident change that turns out to address something that was not happening. The build now measures it instead, once per second while attached, with no behavioural change at all:

```
[climbing] anchor stability frames=… handCorrections=… handCorrectionMax=…
           fitErrorMax=… contactAgeMs=… smoothing=…
```

Read it like this:

- **`handCorrections` close to `frames`** → the hand correction is firing almost every frame. That is the pulsing case, and the fix is to debounce it or drive it from the probe fit rather than from live bones.
- **`handCorrections` low but `fitErrorMax` large** → the root is being yanked when the probe fit refreshes, so the jitter is probe *cadence*, not hands, and the fix is interpolating between fits.
- **Both low while it visibly stutters** → neither of my candidates is right and the cause is outside the anchor maths entirely, which is worth knowing before touching it again.

Moving to `test me`. Climb for ten or fifteen seconds continuously, especially somewhere it stutters noticeably, then stop — a few of those lines is all I need.


## comment 5550152350 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/257#issuecomment-5550152350

Created: 2026-08-15T02:11:49Z; updated: 2026-08-15T02:11:49Z

Exact metadata: [source record](sources/comment-5550152350-6d77fab32c6a80b6b02adaabdc9bee9b14fbe81e17cd59c06963e2b050fc3fbf.json).

Now it's not a jitter. It's like he just flickers into a totally different pose for a split second every half second.
I don't understand. You have the reference mod, no? You decomplied it? It has none of these issues. So how have you failed to fix this so many times now? Just look at how they did it.
