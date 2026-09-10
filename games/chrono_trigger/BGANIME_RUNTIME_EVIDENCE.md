# Chrono Trigger Steam BGAnime runtime evidence gate

This note defines what must be proven before Lexeditor may claim that its scene preview reproduces **Steam runtime chip animation**. It deliberately separates the PC file layout, which is already understood, from animation phase/timing behavior, which is not.

## What is already established

Current PC tooling establishes the descriptor/storage side well enough for read-only diagnostics:

- scene animation data is referenced through the scene/BGSet animation slot;
- Steam uses `Game/field/BGAnime/bganimeinfo_*.dat`;
- PC chip offsets are converted to chip indices with `/32`;
- one animation updates a four-chip destination group from four-chip source groups;
- frame duration is encoded in the upper nibble of the duration byte;
- known upper-nibble duration values are `0x10`, `0x20`, `0x40`, `0x80` -> 16, 12, 8, 4 ticks;
- the lower duration nibble is not assigned meaning by Lexeditor.

Those facts are sufficient for the existing descriptor inspector. They are **not** sufficient to choose the frame visible at scene load or the exact first transition time.

## Why CTViewer is not the runtime oracle

CTViewer contains a coherent viewer-side animation loop, but its state machine is implementation evidence rather than proof of the Steam executable's initialization order.

In particular, the viewer initializes its animation state and advances/copies frames according to its own tick loop. Nothing found in its current source or animation-specific history establishes that the Steam game:

1. copies descriptor frame 0 into the destination group before the scene is first drawn;
2. initially leaves the base destination chips untouched;
3. advances to frame 1 before the first copy;
4. starts the timer before or after an initial copy; or
5. shares a global animation phase between scene loads.

Lexeditor therefore must not infer an initial phase from CTViewer's renderer.

## Evidence required to enable playback

Playback may be promoted from `structural` to `runtime-evidenced` only after a current Steam build supplies an observation that distinguishes the initialization hypotheses below.

Choose at least one scene/animation where:

- destination chips before animation differ visibly or bytewise from descriptor frame 0;
- frame 0 differs from frame 1;
- the duration nibble is one of the already decoded values; and
- the scene can be entered repeatedly from a deterministic transition or save state.

For that animation, collect all of the following:

- scene ID and BGAnime resource path/index;
- destination chip group;
- source chip group for every frame;
- raw duration bytes;
- the four destination chips immediately before the first rendered frame, if obtainable;
- the four destination chips on the first rendered frame, or an equivalent pixel-level capture that identifies the source frame;
- the first frame transition and subsequent transition order;
- whether re-entering the scene restarts or preserves the phase.

A video alone is acceptable only if frame/source identity can be unambiguously matched to decoded chip graphics. A debugger/runtime-memory trace is stronger because it can directly identify the source copied into the destination group.

## Initialization hypotheses to distinguish

### H0 — initial copy of frame 0

At scene initialization, frame 0 is copied to the destination chips and its duration begins immediately.

Expected first visible state: descriptor frame 0.

### H1 — base destination first, then frame 0

The scene initially renders the unmodified destination chips. Frame 0 is copied only after an initial timer interval or animation update.

Expected first visible state: base destination chips.

### H2 — advance before first copy

Animation state starts at descriptor frame 0, but the first update increments the frame before copying.

Expected first animated copy: descriptor frame 1 for animations with at least two frames.

### H3 — externally seeded/shared phase

The initial frame/timer is derived from global or pre-existing runtime state rather than being reset on scene entry.

Expected evidence: repeated entries do not consistently begin on the same descriptor/base frame despite deterministic scene setup.

These labels are test hypotheses only. Lexeditor does not currently claim that any one of them matches the game.

## Timing evidence

Once the initial frame is known, verify at least two consecutive transitions against the decoded duration sequence. Do not convert a duration value to wall-clock seconds unless the runtime tick rate itself is established for this subsystem.

The existing names `ticks` and raw duration values are acceptable structural diagnostics. A future animated preview may use wall-clock timing only after the relevant Steam update cadence is measured or independently documented.

## Composition is a separate gate

Successful BGAnime phase validation does **not** validate scene composition. `PrioMap`, main/sub-screen ordering, per-chip priority and blend/subtract behavior remain a separate PC-runtime evidence problem.

An animated isolated L1/L2/L3 preview could be enabled before full composition only if it is clearly labeled as an isolated layer and its animation initialization/timing has passed this gate.

## Acceptance checklist

Before changing README/Data Map metadata from unsupported to supported, require:

- [ ] current Steam build identified;
- [ ] reproducible scene + animation identified;
- [ ] base destination, frame 0 and frame 1 are distinguishable;
- [ ] first visible/copy state observed;
- [ ] first two transition orders observed;
- [ ] duration order agrees with descriptor records;
- [ ] scene re-entry/reset behavior checked;
- [ ] automated regression fixture added for the chosen initialization rule;
- [ ] desktop/CLI policy text distinguishes isolated animation from composed rendering;
- [ ] no `PrioMap` or blend/priority claim is added as a side effect.

Until every item needed for the claimed behavior is satisfied, Lexeditor keeps BGAnime playback disabled and exposes descriptors read-only.
