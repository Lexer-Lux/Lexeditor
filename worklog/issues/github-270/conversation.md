# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356325612 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270

Created: 2026-08-11T04:23:41Z; updated: 2026-09-05T07:03:59Z

Exact metadata: [source record](sources/issue-5356325612-42a463b280adc029d38f1155713fb99bd087634847d4e6bd38fef9a9ea62bb09.json).

Like this constant bumping, almost sinusoidal. Happens regardless of hi/low mode, all that matters is if he's crouched. What does the log say?

## issue 5356325612 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270

Created: 2026-08-11T04:23:41Z; updated: 2026-09-06T12:57:01Z

Exact metadata: [source record](sources/issue-5356325612-4a0e48f7f6a589bb3df244b0ba3198815946f7561596517bccd30ce46017db88.json).

**Status: The bob is measured; its cause is not confirmed.** Both the camera feature and the physical belt lantern need an isolated comparison.

- [ ] On flat ground, crouch and stand still. Record the bob, then set [Camera] Enabled=0 in GameplayTweaks.ini, restart and repeat at the same place and pose.
- [ ] Restore Camera, disable Belt Lantern for one restart and repeat. Report which change removes the bob, with short clips; restore your original settings afterward.

## issue 5356325612 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270

Created: 2026-08-11T04:23:41Z; updated: 2026-09-06T12:57:01Z

Exact metadata: [source record](sources/issue-5356325612-7df59df193c982459ae1013f9c457a9f1f9e126d30c85baf376e9c463bb720b5.json).

**Status: The bob is measured; its cause is not confirmed.** Both the camera feature and the physical belt lantern need an isolated comparison.

- [ ] On flat ground, crouch and stand still. Record the bob, then set [Camera] Enabled=0 in GameplayTweaks.ini, restart and repeat at the same place and pose.
- [ ] Restore Camera, disable Belt Lantern for one restart and repeat. Report which change removes the bob, with short clips; restore your original settings afterward.

## comment 5550158229 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158229

Created: 2026-08-11T09:32:42Z; updated: 2026-08-11T09:32:42Z

Exact metadata: [source record](sources/comment-5550158229-0b6ee19e24ecc0f926f72bb2c24f66b42bd4ac2d50d8faf1f3cba7b7e8ec38d5.json).

The crouch/aim camera path now requires a stable mode for 100 ms before switching and records raw, applied and final rendered camera values. This is a bounded bob mitigation with enough telemetry to distinguish repeated mode switching from Rockstar camera motion. Test crouched movement and crouched aim; report whether the bob remains.

## comment 5550158259 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158259

Created: 2026-08-14T00:53:49Z; updated: 2026-08-14T00:53:49Z

Exact metadata: [source record](sources/comment-5550158259-32a53bc8209cc48b0beb04fcef6bf20de465f0bd191734c897c030a256f0b3b6.json).

**The mitigation I shipped last time addresses a cause that is not happening.**

That pass added a 100 ms stable-mode dwell, on the theory that rapid stance flicker was causing the bob. Its own success criterion was written into the code: a high `rawFlips` with `appliedFlips` near zero would prove flicker was the source and the dwell had absorbed it.

Your session:

```
rawFlips=64   appliedFlips=62
```

The dwell absorbed **2 flips out of 64**. Essentially every mode change was a real one — you genuinely crouched, aimed, stood — not flicker. So by the criterion I set myself, stance flicker is not the source, and that mitigation was never going to help.

**And the telemetry could not have told either of us that.** `measVertical` moves just as much when you look around as when the camera bobs on its own. Crouched values span 0.91 to 1.82 across your session, and **none** of that spread is attributable, because nothing recorded whether you were moving the camera at the time. I was measuring camera position and calling it bob.

Fixed by recording the look input alongside it. `INPUT_LOOK_LR`/`INPUT_LOOK_UD` are Rockstar's own look actions (`act_bankrobbery01.c:24004-24005`), read through `GET_CONTROL_NORMAL`. Two new fields on every sample:

- `lookIdle=1` — you were not moving the camera on this sample.
- `idleBob` — vertical change since the previous idle sample. That residual is involuntary camera motion, which is the actual subject of this issue.

The next log is then decisive on its own:

- **A run of `lookIdle=1` samples with `idleBob` near zero while crouched** → there is no measurable bob, and whatever you are seeing is not vertical camera drift.
- **A repeating nonzero `idleBob`** → that is the bob, and its size and rhythm say whether it tracks footsteps, breathing or the mode dwell.

Note the crouched sampling already runs at 100 ms, so a walking-cadence bob will show up across consecutive samples rather than being averaged away.

Staying `actionable`. This measures the thing; it does not fix it. But the previous pass was tuning a mechanism the evidence now rules out, and I would rather say that than ship another mitigation aimed at the same wrong cause.


## comment 5550158295 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158295

Created: 2026-08-15T04:13:40Z; updated: 2026-08-15T04:13:40Z

Exact metadata: [source record](sources/comment-5550158295-58c51a28a5b3e4f29984dcad55b66f6f94cc8f3cd15ba3b21cff6e524b41b797.json).

**The bob telemetry ran, and it measured essentially nothing — but the sample is too thin to call it.**

The `idleBob` field records how much the rendered camera moves vertically while you are NOT moving the look stick, which is the only way to separate real camera bob from you simply looking around. Across the whole session its values are:

```
idleBob = 0, 0.000152, 0.000167, 0.000183, 0.000190
```

Peak about **0.0002**. That is not a bob; that is numerical noise.

`measVertical` by mode, for context:

| mode | samples | min | median | max |
|---|---|---|---|---|
| STANDING | 698 | 0.019 | 1.155 | 4.554 |
| CROUCHED | 45 | 0.517 | 1.202 | 1.806 |
| AIM | 39 | 0.732 | 1.145 | 1.331 |

Crouched spans 0.52–1.81, but with `lookIdle=1` on 684 samples and `idleBob` at noise level, that spread is you looking around, not the camera moving on its own.

**Why I am not closing this.** You only crouched for about 45 samples — roughly twenty seconds — and the bob you described is intermittent. Twenty seconds of crouching is not enough to conclude it is gone, and I am not going to tell you a problem is fixed on that basis.

Also confirmed dead: the stance-flicker theory. `rawFlips=56 appliedFlips=56` — the 100 ms dwell absorbed **nothing**, so every mode change was real. By the criterion written into that mitigation, flicker was never the source. That matches the previous session (64/62) and it is now twice-confirmed.

Staying `actionable`. Next time you are crouched, stay crouched and move around for a minute or so without touching the look stick. If `idleBob` stays at noise while you can see the bob, the bob is not in the camera transform this module controls and the fix is somewhere else entirely.


## comment 5550158325 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158325

Created: 2026-08-19T11:54:59Z; updated: 2026-08-19T11:54:59Z

Exact metadata: [source record](sources/comment-5550158325-2ba1af8515b899e7e410ba43b0537c9ae49fddf13710261b8224d7269adb312a.json).

**You're right, and my last comment on this was wrong.**

I told you `idleBob` was "numerical noise" at a peak of 0.0002. In your latest log the same field reaches **0.015 to 0.027** while you are crouched and not touching the look stick. The earlier session simply had almost no crouched play in it, so I called an absent sample a negative result. That's the exact thing this project's rules say not to do, and I did it.

**What your log shows now.** Between +122.6s and +126.4s you are crouched, idle, and not moving the camera. Every value the mod submits is frozen for that whole window (`sentDistance=1.85 sentHorizontal=0.42 low=0`, `rawFlips` unchanged). The rendered camera height still does this:

```
0.9030  0.8936  0.8952  0.9116  0.9105  0.9052  0.9083  0.9147  0.9261  0.9111
0.9160  0.9263  0.9177  0.9172  0.9175  0.9080  0.9154  0.9194  0.9244  0.9129
```

About 33 mm of movement, repeating roughly every 0.4 seconds. That is your bob, and it is real. It is also **not** the stance-flicker theory from two rounds ago — nothing the mod submits moved at all while that was happening.

**Why I still can't tell you what's moving.** The number I was measuring is *camera height minus Arthur's height*. A bobbing camera over a still Arthur and a still camera over a bobbing Arthur produce the identical number. On top of that, crouched was sampled 5x faster than standing, so the two could never be compared. That measurement was never going to answer this.

It now records the two heights **separately**, sampled every frame, over a window that is the same length in every stance. Next log:

- `camZP2P` big, `pedZP2P` small → the camera is bobbing on its own. Mine to fix.
- `camZP2P` ≈ `pedZP2P` → the camera is faithfully following Arthur's crouch breathing animation, and the fix is not in the camera at all.

**One real candidate fixed in the same change.** The mod was calling the game's ground-level camera function every single frame. Rockstar's own note on that function says "must be called every frame to interpolate — **pass false to reset**". Your crouched profiles are all NORMAL, so the mod was firing that *reset* about sixty times a second at an engine that was mid-interpolation. A per-frame reset against a per-frame interpolation is a wobble, and it would only show up in the stance where the game actually wants the low framing — crouched, which is exactly what you reported. LOW is still asserted every frame because the function requires it; NORMAL is now released once, at the transition, and then the game is left alone.

I am not claiming that fixed it. It's a genuine candidate with a documented mechanism, and the new measurement is what decides.

**Also gone from the crouched path:** the shoulder-mirror probe I left running was yanking the camera 0.57 m sideways on every crouch/stand change. Details in Lexer-Lux/Lexeditor#267.

**What to do when this build lands:** crouch, stay crouched, walk around for a minute without touching the look stick. Then crouch and stand still. The log line to look at is `camZP2P` / `pedZP2P`.

Moving this back to `actionable` — it is not fixed, and it should never have been sitting on `test me` after you told me it was still happening.


## comment 5550158365 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158365

Created: 2026-08-20T01:35:19Z; updated: 2026-08-20T01:35:19Z

Exact metadata: [source record](sources/comment-5550158365-bc0fc502e13bcc693e9e3711a6670b3b1cb7785838e618dad415f112b8dbe09b.json).

**The instrumentation from the last round did its job. The bob is real, it is crouch-specific, and it is the CAMERA moving, not the ped.**

Filtered to genuinely idle frames — `lookIdle=1` and ped vertical movement under 5 mm, teleports discarded:

```
STANDING idle   n=454   median camZP2P = 0.0005 m
CROUCHED idle   n=103   median camZP2P = 0.0471 m
```

Roughly **90x more camera movement while crouched, with the ped provably motionless**. That is exactly what Lexer has been reporting, and it is the first time the two have been separated — the old metric was `camZ - pedZ`, in which a bobbing camera and a bobbing ped are indistinguishable.

Splitting it further:

| crouch | low | n | median camZP2P |
|---|---|---|---|
| 0 | 0 | 341 | 0.0034 |
| 1 | **0** | 73 | **0.0922** |
| 1 | 1 | 29 | ~0.018 |

**What is now ruled out, with evidence rather than reasoning:**

- **Not the transition smoothing.** 97 of the 103 crouched idle samples have `txProgress >= 0.999` — the transition is settled — and still bob 4.7 cm.
- **Not the low-camera flag toggling.** Only 6 changes across 279 crouched samples, stable for minutes between them. It is not oscillating.
- **Not this module writing height.** The only per-frame camera write is `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE`, which takes a horizontal offset and a distance. It has no vertical term. The module's ONLY vertical control is the low-camera boolean, and that is stable.
- **Not a named camera shake.** The shake names in `script_rel` are explosion, drunk, wind, lasso and minigame effects; none is a crouch or idle shake.

**So the vertical motion originates outside this module's writes.** The most likely remaining source is the crouched idle animation itself — the third-person camera follows the ped, and a crouched breathing idle moves what it follows while the root position stays put, which is precisely the signature here (`pedZP2P` ~0.0001 m at the root while the camera moves 90x that).

I am not going to assert that as fact without the test that settles it, and it is a cheap one:

**Set `[Camera] Enabled=0` in `GameplayTweaks.ini`, crouch, and stand still.** If the bob is still there with the feature off, it is vanilla RDR2 and this issue should be closed as unfeasible or reframed. If it disappears, the cause is in this module despite everything above, and the measurement narrows to what changes when the feature is enabled.

**The one lever that exists in the meantime:** the low camera cuts the bob about five-fold (0.092 -> 0.018). `CrouchedLowCamera` is a setting Lexer owns, so I have not changed his framing for him — but if he wants the bob reduced now and can live with the lower crouched framing, that is the switch.

Moving to `needs a human`: the next step is his decision or his test, not more code from me.


## comment 5550158396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/270#issuecomment-5550158396

Created: 2026-08-20T12:57:27Z; updated: 2026-08-20T12:57:27Z

Exact metadata: [source record](sources/comment-5550158396-a72f528554109f378dbf419e069711030ff9a800ddcb601afac6bc1d9b25d727.json).

New likely cause to test: the physically rigged lantern may touch the ground while Arthur is crouched. The current prop becomes world-collidable after calibration, is jointed at PH_Belt_Thrower, and its body hangs about 0.22 m below the grip. That can produce camera motion while the ped root remains still, so it fits the existing trace. It is not confirmed yet. A direct comparison with the lantern stowed, followed by the same crouched idle pose, will separate lantern collision from camera behavior. If confirmed, the repair belongs to the lantern placement rather than camera interpolation.
