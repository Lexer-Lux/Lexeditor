# GitHub #32 - Customize casing glint FX

## Requirement

The six casings dumped by a revolver reload must not flash in lockstep. The
effect needed a longer, larger and subtler default appearance, with every
genuinely controllable visual dimension exposed for Lexer to tune.

## Trace and editable surface

The synchronized flash was the ASI-created looped particle
`scr_generic` / `scr_event_glint`, attached to every physical casing in
`items_casings.cpp`. It was not an immutable model or pickup effect. RDR2's
native surface exposes live looped-particle scale, RGB colour and alpha, while
the ASI controls when the handle starts and stops. Therefore all requested
dimensions are genuinely editable:

- timing and randomness: independent per-casing start times and randomized
  pauses;
- duration: scripted pulse lifetime;
- size: `SET_PARTICLE_FX_LOOPED_SCALE`;
- brightness: equal RGB multipliers through
  `SET_PARTICLE_FX_LOOPED_COLOUR`;
- transparency: `SET_PARTICLE_FX_LOOPED_ALPHA`;
- fade: a per-frame alpha envelope with separate fade-in and fade-out times.

The relevant native declarations are present in the bundled RDR2 SDK. No
unverified particle-evolution parameter or invented asset name was needed.

## Implementation

Each `SpentCasing` now owns `glintStartedAt` and `nextGlintAt`. Creation assigns
an independent random initial phase, which directly breaks a same-frame
revolver dump's synchronization. Each pulse starts the real attached effect,
updates size, brightness and alpha live, stops after the configured duration,
then schedules a randomized pause. Turning glints off stops active handles;
turning them back on retains independently seeded phases.

The shipped `[SpentCasings]` section exposes:

- `GlintSize=1.5`
- `GlintAlpha=0.45`
- `GlintBrightness=0.75`
- `GlintDurationMs=1200`
- `GlintFadeInMs=250`
- `GlintFadeOutMs=450`
- `GlintPauseMs=1600`
- `GlintTimingRandomnessMs=1000`

The size and duration defaults are increased from the former glint, alpha and
brightness are reduced, and timing randomness is enabled. The generic in-game
settings editor discovers these INI keys automatically. Values are clamped on
config load and take effect after restart.

Issue #45's weapon-relative spawn matrix, initial velocity, tumble, inherited
ped velocity, reload fan and collision behavior were not changed.

## Integration and runtime acceptance

The integration owner must run
`python tools/reverse-engineering/verify_casing_glint_issue_32.py`, then perform
the unified build, install and game-root hash verification. After installation,
move issue #32 from `actionable` to `test me`.

In game, dump a full revolver cylinder and confirm the six glints begin at
different times rather than flashing together. Confirm they are visibly larger
and longer but less harsh than before, remain centered on moving/settled
casings, fade smoothly, and stop when the casing is collected or expires.
Change each of the eight settings (restarting after edits) and verify the
expected independent effect. Also fire/cycle several weapon classes and confirm
#45 ejection direction, momentum, tumble and collision remain unchanged.

Static verification proves the control plumbing and native surface, not the
final visual tuning inside RDR2. Build, installation, relabeling, commit and push
were intentionally left to the integration owner.
