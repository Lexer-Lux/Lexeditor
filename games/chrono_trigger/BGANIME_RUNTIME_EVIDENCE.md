# Chrono Trigger Steam BGAnime runtime evidence gate

Lexeditor can decode the current-PC BGAnime descriptor structure, but **animated scene playback must remain disabled** until the Steam runtime's initial chip state, first-frame copy and timer phase are independently observed.

CTViewer is useful structural evidence, but its renderer behavior is not by itself proof of the retail Steam runtime.

## Structurally established PC data

- Scene `chipAnimations` selects `Game/field/BGAnime/bganimeinfo_<index>.dat`.
- The PC resource begins with an animation-count byte.
- Each animation declares a frame count; `0x00` and `0x80` terminate descriptor reading.
- Destination/source offsets identify the first of four animated chips and are converted to chip indices with `/32` on PC.
- Each frame carries a duration byte and source offset.
- The documented duration upper nibble maps `0x10/0x20/0x40/0x80` to `16/12/8/4` ticks.
- The lower duration nibble remains uninterpreted.

These facts are sufficient for structural inspection, not playback.

## Runtime hypotheses that must be distinguished

A real Steam-runtime capture must establish which initial-state model is correct before Lexeditor renders an animation timeline:

- **H0 — base graphics first:** destination chips initially contain the ordinary L1/L2 tileset data and no animation source is copied until the first timer expires.
- **H1 — frame 0 copied on load:** frame 0 source chips replace the destination group immediately when the scene/tileset initializes; its duration then begins.
- **H2 — frame 0 copied on first tick:** base graphics survive initialization, but frame 0 is copied on the first runtime animation tick before a full duration elapses.
- **H3 — pre-advanced phase:** the scene begins at another frame/timer phase because animation state is global, inherited, seeded or advanced during loading.

If the runtime exhibits a different model, record that model instead of forcing it into H0–H3.

## Minimum acceptance capture

Use a scene with a BGAnime entry whose four destination chips differ visibly from every candidate source frame. Record enough information to distinguish actual chip state, not only a subjective screenshot.

For at least two separate scene entries/reloads, capture:

1. scene ID and `chipAnimations` index;
2. exact BGAnime descriptor bytes for the tested animation;
3. base graphics bytes for the four destination chips;
4. source graphics bytes for every frame's four-chip source group;
5. the first observable rendered state after location initialization;
6. each subsequent distinct state until the animation wraps at least once;
7. elapsed frame/tick timing between state changes;
8. whether leaving and re-entering the location resets or preserves the phase.

Prefer a deterministic capture from a runtime hook, debugger, texture/chip-buffer dump or other direct state observation. Timestamped video may supplement that evidence but should not be the sole source if initialization happens before the first reliably captured frame.

## Acceptance criteria for playback

Playback may be enabled only after the evidence establishes all of the following for the current Steam build:

- which source frame, if any, is copied during initialization;
- the exact ordering of first copy vs first timer decrement/expiry;
- frame-advance order and wrap behavior;
- whether duration values represent the observed runtime interval and at what tick basis;
- whether animation phase is reset per scene load or can be inherited/shared;
- whether multiple BGAnime groups tick independently or share a phase/timer;
- how a zero/terminator frame-count form behaves at runtime if one is encountered.

The implementation must then add a synthetic regression that proves the chosen initialization, timing and wrap policy. Until that exists, scene metadata must continue to report animation playback as unsupported/disabled.

## Composition remains a separate gate

Even after BGAnime chip mutation is proven, a composed Steam scene renderer must **not** be claimed until current-PC layer ordering, `PrioMap`, main/sub-screen flags and blend/subtract behavior are independently established.

An animated isolated L1/L2 raster may be implemented before composition only if it is explicitly labeled isolated and the runtime animation criteria above are satisfied.

## Current status

**Structural descriptor decoding: supported.**

**Runtime animation playback: unsupported pending the observations above.**

**Main/sub/priority composition: unsupported pending separate PC-runtime evidence.**
