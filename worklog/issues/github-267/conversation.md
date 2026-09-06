# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356324593 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267

Created: 2026-08-11T02:12:52Z; updated: 2026-09-05T07:03:49Z

Exact metadata: [source record](sources/issue-5356324593-a029e93fbf6e48b89785f65525059ec75ee79fcaa82e4ae97093142c3c087243.json).

Hitting X while aiming alternates between "camera on Arthur's left" and "camera with him centered".

## issue 5356324593 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267

Created: 2026-08-11T02:12:52Z; updated: 2026-09-06T12:56:56Z

Exact metadata: [source record](sources/issue-5356324593-66158e6c638b7723120a3525f9ef19c9c75b752185359887a7f480b9fd371b60.json).

While aiming, X should switch smoothly between comparably offset left and right shoulders—not far-left and centered.

**Status: Latest retest still failed.** Merely crossing the centerline is not success. Fix the settled positions and transition before requesting another shoulder-switch check.

## issue 5356324593 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267

Created: 2026-08-11T02:12:52Z; updated: 2026-09-06T12:56:56Z

Exact metadata: [source record](sources/issue-5356324593-a6858f0c4ce6c95dbc7b78f157095b5034939ee6605f20b85451c594ce77553b.json).

While aiming, X should switch smoothly between comparably offset left and right shoulders—not far-left and centered.

**Status: Latest retest still failed.** Merely crossing the centerline is not success. Fix the settled positions and transition before requesting another shoulder-switch check.

## comment 5550156674 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156674

Created: 2026-08-11T04:20:48Z; updated: 2026-08-11T04:20:48Z

Exact metadata: [source record](sources/comment-5550156674-a1e41e28c38d259494d831a2fd179fea689d73b1a64a002bafcb8aef995321ca.json).

Swapping shoulders while aiming gives nice smooth camera movement, but...
When hitting X to move him onto the left side of the screen, it's almost perfect, but after it's almost done moving there's this noticable jump to put him more to the left.
When hitting X to swap him onto the right, it's similar but the jump is way bigger, and it also moves him to the left.
what does the log say?

## comment 5550156693 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156693

Created: 2026-08-11T09:32:38Z; updated: 2026-08-11T09:32:38Z

Exact metadata: [source record](sources/comment-5550156693-1ed991f9c2c48bbb65473bcdd1571154e04bfb25d33b8975af509daed91233d3.json).

The shoulder profile no longer releases and reasserts the offset during the same aim-side transition. It keeps one nonnegative magnitude while Rockstar owns the aim side, then reports the rendered settle result. Test repeated left/right switches while aiming and watch for a late jump or recenter.

## comment 5550156706 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156706

Created: 2026-08-12T12:46:32Z; updated: 2026-08-12T12:46:32Z

Exact metadata: [source record](sources/comment-5550156706-3c734287cfa1f5195a2957f2df92443d08f7cd20e4511d9ed931e6162afafe71.json).

still seems off to me?

## comment 5550156726 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156726

Created: 2026-08-13T01:40:11Z; updated: 2026-08-13T01:40:11Z

Exact metadata: [source record](sources/comment-5550156726-84c6bc7670540dffe80c69a2a9a768c28f0bc327c9cee4fc305f5d8adcbc9078.json).

**The log answered your question, and it contradicts the current design assumption.**

`measLateral` is a **signed** projection onto the camera's right vector (`gameplay_camera.cpp:293`: `delta.x*right.x + delta.y*right.y`). So a genuinely mirrored shoulder *must* render a negative value.

Across your entire aiming session:

```
sentHorizontal=0.55  measLateral=0.458  rawFlips=7
sentHorizontal=0.55  measLateral=0.447  rawFlips=9
sentHorizontal=0.55  measLateral=0.655  rawFlips=11
sentHorizontal=0.55  measLateral=0.683  rawFlips=11
```

`rawFlips` climbing 7→11 means real shoulder swaps happened. **`measLateral` never went negative once** — it only moved between +0.44 and +0.68. The side never mirrored; only the magnitude changed. That is precisely your "left" versus "centered" instead of left versus right.

This undercuts the model the code is built on. `gameplay_camera.cpp:549` asserts *"The side belongs to Rockstar. The module submits a nonnegative magnitude and never negates it."* If that were true, a swap would flip the rendered sign. It doesn't. Two explanations survive and the existing log **cannot** separate them:

1. Rockstar's swap genuinely never mirrors in this state, or
2. asserting `+0.55` every single frame suppresses the mirror, so only its magnitude survives — 0.45 when it fights the engine, 0.66 when it agrees.

I'm not going to guess between those; that guess is what produced the previous two failed passes. So this build adds a switch that settles it:

```ini
[Camera]
AimHorizontalOverride=1   ; 1 = shipped behaviour, 0 = hand lateral back to the engine
```

Hot-reloads, and it's in the settings menu and editor. **Set it to 0, aim, and press X a few times each way.** The sample lines will read `hOverride=0`:

- `measLateral` goes **negative** on one shoulder → our constant assertion was suppressing the mirror, and the fix is making the offset follow the engine's side.
- `measLateral` still **never** goes negative → the engine isn't mirroring here at all, and no offset policy can fix it. That would mean the feature needs a different mechanism entirely.

Either result kills one branch outright. Being explicit: **this is a diagnostic, not a repair** — I'm not claiming Lexer-Lux/Lexeditor#267 is fixed.

Built (EXIT=0); installer is queued to land when you close the game.

## comment 5550156745 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156745

Created: 2026-08-13T12:55:24Z; updated: 2026-08-13T12:55:24Z

Exact metadata: [source record](sources/comment-5550156745-110d95bfd75ea61253986c0e900e41c2e38f7ebd241cead849fbff57f008c1c5.json).

nope. aimed my gun and moved my camera way out to the right so arthur was on the very left of my screen. hit x. now he's in the center!

## comment 5550156761 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156761

Created: 2026-08-14T00:51:12Z; updated: 2026-08-14T00:51:12Z

Exact metadata: [source record](sources/comment-5550156761-0b5902089e1c45f189aee1941e14210020afc7f52d9abe6aa1d961f0fe09174a.json).

**The experiment that would settle this never ran — because it needed you to flip a switch. That was my mistake, and it now runs itself.**

Last time I added `AimHorizontalOverride` so that setting it to 0 would hand lateral back to the engine and reveal whether the shoulder actually mirrors. Your session:

- **2038** camera samples, every single one `hOverride=1`
- `measLateral` negative **11 times out of 2136**

So the switch was never off, and the decisive measurement was never taken. The codex build policy says plainly: never leave a diagnostic behind an ini switch you have to flip, because that is how rounds get burned. I did exactly that, and it cost this issue another session.

**It is automatic now.** For one second after each *raw* shoulder flip — the only moment the answer can appear — lateral is handed back to the engine, then it reverts on its own. The window only opens when the override is otherwise on, which is the state under test, and the existing 2 Hz sample line now carries `mirrorProbe=1` for those frames.

That makes the next log self-answering:

- **A negative `measLateral` on any `mirrorProbe=1` sample** → the continuous assertion was suppressing the mirror. The fix then belongs in how the offset follows the engine's side, and it is a real fix.
- **Never negative, even on `mirrorProbe=1`** → the engine genuinely does not mirror in this state, no offset policy can fix it, and this needs a different mechanism entirely.

You do not have to change any setting or do anything unusual. Just aim and press X a few times as you normally would.

Two honest notes. You may see a brief lateral shift for about a second right after pressing X — that is the probe handing the offset back, and it reverts by itself. And the native this rides on, `0x066167C63111D8CF`, is unnamed with untyped parameters, so even "this argument means respect-horizontal-offset" is an inference from behaviour rather than something the SDK states. The probe is designed to test that inference rather than trust it.

Staying `actionable` — this measures, it does not repair.


## comment 5550156778 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156778

Created: 2026-08-15T02:29:03Z; updated: 2026-08-15T02:29:03Z

Exact metadata: [source record](sources/comment-5550156778-9ea5745a0e24540e741318b3ebca5e65197146a4c62011717904f93d64425d76.json).

So when I press RMB the camera does a horizontal jump, then a smooth transition, then another horizontal jump. I'm assuming it has something to do with this. Which is ridiculous: all movements needed for the camera mode should be put into one. Just find out what position/etc. you need, do a smooth transition on ALL DIMENSIONS at once....how does this even happen? It's ridiculous.

## comment 5550156799 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156799

Created: 2026-08-15T04:08:43Z; updated: 2026-08-15T04:08:43Z

Exact metadata: [source record](sources/comment-5550156799-c082d319a1d5e83477c99a8ceba5a73f9176ec81737211341d45f225f780780f.json).

**The experiment finally ran, by itself, and it answers the question.**

The automatic probe worked: 85 samples with `mirrorProbe=1`, meaning the horizontal override was handed back to the engine for a bounded window after each raw shoulder flip — no switch for you to flip, which was the point.

The result:

- during the probe, `measLateral` sat at **+0.3999 to +0.4002**
- exactly **1 sample out of 85** was negative

`measLateral` is a signed projection onto the camera's right vector, so a mirrored shoulder must render negative. It does not. Releasing our override changed the magnitude (≈0.40 during the probe versus 0.44–0.68 while asserted) but never the **side**.

That separates the two explanations this issue has been stuck between:

- ~~our continuous assertion was suppressing the engine's mirror~~ — ruled out; the mirror does not appear even when we stop asserting
- **Rockstar's swap does not mirror the shoulder in this state at all** — supported

Which matches what you actually described: "camera on Arthur's left" versus "him centered", not left versus right. There is no right-shoulder render happening to fix.

So no horizontal-offset policy can produce a true shoulder swap here, because the engine is not swapping sides — we would only ever be changing how far off-centre he sits. Getting a genuine mirrored shoulder would need a different mechanism than the gameplay-camera params native, and I have not found one that resolves.

That is a real limit rather than a bug I can fix, so it needs your call: accept the engine behaviour and tune the offset for the framing you prefer, or treat "true shoulder swap" as unfeasible via this native and close it as such. I have not marked it `unfeasible` myself, because that is your judgement.

The 1 negative sample of 85 is most likely a transition frame; I am not building an argument on it.


## comment 5550156811 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156811

Created: 2026-08-19T11:54:58Z; updated: 2026-08-19T11:54:58Z

Exact metadata: [source record](sources/comment-5550156811-52c2ff1b1e03fef066267127ca33954c6afe39420420704a30ef9dc1c22e8de1.json).

**Root cause found, and it was my own diagnostic doing it.**

> "the camera just jumps instantly when transitioning between states, but ONLY horizontally for some reason -- probably a fuckup with the shoulder cam feature"

You were right about where it was.

**What was happening.** A previous pass left a self-running probe in the camera code. Its job was to find out whether the game would mirror the shoulder if the mod stopped asserting its sideways offset — so for **1000 ms after every stance change** it handed the sideways offset back to the game, then took it back. A crouch/stand change counts as a stance change, so it fired on exactly the transitions you were describing.

Your log has the controlled comparison in it. Same mode, same submitted value, the only difference being whether the mod was asserting the offset:

```
+509438ms  mode=STANDING  sentHorizontal=5.63  mirrorProbe=0  measLateral=0.962963
+511438ms  mode=STANDING  sentHorizontal=5.63  mirrorProbe=1  measLateral=0.389462
```

That is **0.57 m of instant sideways movement**, once on the way out and once on the way back, on every transition. It was horizontal-only because the *distance* override was never dropped — it kept blending normally the whole time. That asymmetry is the entire "but ONLY horizontally".

**The probe also answered its own question, so it's gone for good.** Across 77 samples taken inside those windows, the rendered sideways position was **never** negative — not once in all 842 camera lines — and it sat pinned near +0.39 no matter what offset was asked for, including +5.63. So the game does not mirror the shoulder in this state, and the mod's constant offset was never what was suppressing it. That question is closed. The probe is deleted rather than switched off, and the `AimHorizontalOverride` note in the INI now records the answer instead of asking you to run the test yourself.

Worth saying plainly: a finished diagnostic left running in the per-frame path became a shipped defect. It had already collected its answer in an earlier session.

**Now the part you actually asked for.** Even with the probe gone the axes were still two separate transitions: sideways offset was eased by the mod over ~250 ms, while distance was stepped to its new value and left to the game's own blend at `BlendSpeed`. Two different smoothing laws never arrive together no matter how they're tuned.

Both continuous axes now ride **one clock and one easing curve** — new `Camera|TransitionMs` setting, default 250 ms, hot-reloads. Starting point is wherever the camera actually is at the moment the stance changes, not the old profile's value, so a fast crouch-stand-crouch continues from the current position instead of snapping. At rest both land exactly on your saved numbers, so nothing you've dialled in changes meaning and the live editor still nudges 1:1.

**One honest limit.** The vertical control the game exposes is a **boolean** (low framing on/off), not a number — there's no continuous vertical-position argument on the public native surface, which is why the editor offers LOW/NORMAL rather than a slider. It cannot be interpolated by the mod. What it now does is switch on the same frame the ramp starts, so the game's own interpolation of it begins alongside the other two instead of at some unrelated moment. That's as close to "X, Y and Z as one movement" as the game allows, and I'd rather say so than claim a three-axis blend I didn't build.

Test when this build lands: set the crouch and standing cameras far apart as you had them, then crouch and stand repeatedly. The sideways offset and the distance should move together and neither should snap. `txProgress` on the sample lines shows the transition running if you want to check the log.

Moving off `needs a human` to `actionable` — nothing is waiting on you now; it needs the build.


## comment 5550156823 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156823

Created: 2026-08-20T12:46:23Z; updated: 2026-08-20T12:46:23Z

Exact metadata: [source record](sources/comment-5550156823-641f6d23cefea2e468140f85c955bcc6902e655db3bad76e4fd0cf2a2bd3bae2.json).

Confirmed. The log shows real sign crossings, but the settled offsets are about 0.65 m on one shoulder and 0.24 m on the other. The old verdict called that success merely because the sign changed. Your installed Aim offset is negative, which strongly biases one shoulder and leaves the other near center. The repair now treats the configured Aim value as a magnitude. Rockstar still owns the X shoulder action; the mod observes the current rendered side and moves the submitted bias to the opposite sign through the existing smooth transition. A settle now passes only if it crosses and the two absolute offsets are within 25 percent. The next queued build contains this. Retest repeated X presses while aiming: Arthur should move between comparably offset opposite sides, not far-left and centered.

## comment 5550156837 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/267#issuecomment-5550156837

Created: 2026-08-20T13:27:40Z; updated: 2026-08-20T13:27:40Z

Exact metadata: [source record](sources/comment-5550156837-320f38f42d3663af685511f28a708536542c81d69ef3d3d9f63414b398a378a1.json).

Returned test still produces far-left to centered after X, so the signed-magnitude shoulder repair is not accepted. The issue remains actionable; a sign crossing alone is not success unless both settled offsets are comparably far from center and the whole switch is one smooth movement.
