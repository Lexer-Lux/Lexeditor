# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356301343 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177

Created: 2026-08-06T03:32:27Z; updated: 2026-09-05T06:58:55Z

Exact metadata: [source record](sources/issue-5356301343-5c18183c09cb6c9a9379118a31bd92f9cd7581a0e80b422941af9f0fd660671b.json).

## Observation
The red fill animation when Health, Stamina, and Dead Eye cores restore or drain is visibly choppy, including in vanilla RDR2.

## Findings
- Core state is quantized before the HUD receives it. Rockstar's native surface exposes `_GET_ATTRIBUTE_CORE_VALUE` as an integer on a 0–100 scale, and `_SET_ATTRIBUTE_CORE_VALUE` also accepts an integer.
- Rockstar's consumable scripts calculate a float target but call `CEIL(target)` before writing the core. Vanilla therefore cannot provide fractional core states for the HUD to render.
- The game archive contains numbered `EFFECT_HEALTH_CORE_01…08`, `EFFECT_STAMINA_CORE_01…08`, Dead Eye equivalents, and similar horse entries. Those names are consumable-effect tiers; they do **not** prove the HUD swaps eight fill textures.
- The same scripts publish `HealthCoreValue`, `StaminaCoreValue`, and `DeadEyeCoreValue` around consumption and set the final integer core. This suggests a separate presentation/notification path exists, but no public native was found that controls only the vanilla core widget's displayed fill.
- The outer bars are not all constrained the same way: Stamina and Dead Eye expose floating-point amounts, while cores are explicitly integer. They are therefore not evidence of the same discrete-art mechanism.
- GameplayTweaks' CoreClock also accumulates fractions and writes only whole core points because the engine cannot store a fractional core. Large sleep/refill changes can be distributed as one-point writes, but that would tween the real gameplay state rather than merely the picture.

## Current conclusion
The choppiness is confirmed to have a numeric cause: only 101 real core states exist, and vanilla rounds writes. It is **not yet confirmed** that the HUD fill itself is made from separate staged art assets.

A partial fix is feasible: queue large core changes and apply their integer points at evenly spaced intervals. That would look smoother, but restoration/drain would take time mechanically as well. A presentation-only fix would require either finding an internal input to the vanilla HUD movie/widget or replacing/hooking the widget. No supported native currently exposes such a display-only value, and a replacement overlay is outside scope.

## Remaining research
Inspect the actual HUD GFX/texture resources and determine whether the fill uses a mask/timeline or staged frames. This extraction must wait until RDR2 is closed because OpenIV and the game must not access the archives concurrently.

## Constraint
Research only. Do not implement or add a HUD overlay without a later decision.

## issue 5356301343 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177

Created: 2026-08-06T03:32:27Z; updated: 2026-09-06T12:55:00Z

Exact metadata: [source record](sources/issue-5356301343-a4ba961b2bd5653c4058c370af1bfb7003bb1ca63d4c3c25a9fcbe9ecafce958.json).

**Status: Static research and HUD extraction are complete.** The core artwork has 16 staged states; repeating the OpenIV inspection is unnecessary.

The remaining question needs a synchronized core-value trace and video to distinguish artwork stepping from update timing. Prepare the recording tool and exact restoration/drain sequence first. No smoothing change is ready to test.

## comment 5550129676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177#issuecomment-5550129676

Created: 2026-08-06T03:56:51Z; updated: 2026-08-06T03:56:51Z

Exact metadata: [source record](sources/comment-5550129676-1af6dec6323e50f68b2cb6dc023047959340114f6f2313a9fbb29cc02a8d9411.json).

The prior conclusion still holds after cross-checking the codebase: cores are integer 0–100 state, and CoreClock accumulates fractions but writes whole points. Timed one-point writes can soften large jumps, but they delay the real gameplay change and are not display-only smoothing. No supported native exposes a separate fractional fill for the vanilla widget. The decisive remaining step is game-closed inspection of the actual HUD movie/resources to determine whether the fill is a mask/timeline, staged frames, or code-driven. Do not ship a gameplay tween or overlay as if it solved the vanilla HUD.

## comment 5550129692 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177#issuecomment-5550129692

Created: 2026-08-06T04:54:32Z; updated: 2026-08-06T04:54:32Z

Exact metadata: [source record](sources/comment-5550129692-c3982fb2413200765d5f0f441295ec619cb49f7f697de529be8f02da2a2d7598.json).

okay but none of this answers the question."queue large core changes and apply their integer points at evenly spaced intervals" ??????? like yeah, if you do something that regens half your HP obviously your HP jumps to +50. how is that even a problem? most games work that way. the issue is things that should drain or restore bars in tiny continuous amounts -- like stamina regen/drain, just don't. they do it in chunks. why?

So is the problem the fact that it can only change in increments of ~3.6 degrees or so? Is that even perceptible? Can we overwrite this base game code to treat these like floats so continuous drain/restoration, like with stamina, is actually continuous?

## comment 5550129699 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177#issuecomment-5550129699

Created: 2026-08-06T07:43:24Z; updated: 2026-08-06T07:43:24Z

Exact metadata: [source record](sources/comment-5550129699-e59d446f435d75d392e3434da9c7cff06c6e1405b281761c1781c2bf685b19a1.json).

Answering the actual question: yes, the core's exposed state really is integer-only, so a full circle has at most 101 positions (about 3.6 degrees per point). The getter returns an integer and the setter accepts an integer; Story Mode repeatedly rounds/ceils float calculations before `_SET_ATTRIBUTE_CORE_VALUE` (for example `short_update.c` at 18049-18051 and 112637). ScriptHook cannot change that backing engine field to a float. Passing a float would only be converted to the native's integer parameter.

That does **not** prove the visible chunking you describe is only one-point/3.6-degree quantization. One-point steps may be perceptible on a small high-contrast radial fill, but if the observed motion jumps several points or waits conspicuously between updates, there is an additional cadence/presentation effect. The vanilla scripts show float accumulation followed by rounded integer writes; the HUD may also sample or tween those writes internally. Static script/native evidence cannot distinguish those visually.

Therefore:
- We cannot overwrite the vanilla core state as a float through the supported native surface.
- Rewriting slow drain/regen to emit integer changes as soon as each 1% boundary is crossed can prevent *multi-point* batching, but cannot create fractional core states and should not be called a complete smoothing fix.
- The decisive test is a controlled runtime trace: log the integer core every frame beside a video of a slow vanilla drain/restore. If the number changes 1 at a time while the art jumps in larger/less frequent chunks, the problem is HUD presentation. If the number itself changes in chunks, the producer cadence is the problem.
- A display-only solution still requires inspecting/hooking the HUD movie/widget; it cannot be obtained by changing the public core setter.

Research is complete to the supported-static boundary. Human/runtime work remains: the synchronized trace/video and, with the game closed, HUD resource inspection. No gameplay tween or overlay was implemented.

## comment 5550129710 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/177#issuecomment-5550129710

Created: 2026-08-13T00:49:10Z; updated: 2026-08-13T00:49:10Z

Exact metadata: [source record](sources/comment-5550129710-e831abae333b755d4843216374bf4d06923b9791f295cce1440a044b5f5c4a1e.json).

I completed the game-closed OpenIV inspection. The HUD archive has 100 staged outer-meter textures (rpg_meter_0 through rpg_meter_99), but each Health, Stamina, Dead Eye, and horse core has only 16 staged core_state textures. So the core art itself is quantized to 16 states; it is not one continuously masked fill texture. The 01-08 consumable-effect art is separate. The remaining question is whether internal HUD code interpolates those 16 states or whether producer cadence causes the visible chunks, so the synchronized runtime trace/video is still required. I left this as needs a human.
