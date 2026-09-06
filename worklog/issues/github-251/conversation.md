# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356319949 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251

Created: 2026-08-10T15:28:55Z; updated: 2026-09-05T08:11:17Z

Exact metadata: [source record](sources/issue-5356319949-4ffd977c43edf2011dc1c9778cc14ba1f87663ee73bb8a867c156dc80717d2b9.json).

(No body was present in this captured version.)

## issue 5356319949 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251

Created: 2026-08-10T15:28:55Z; updated: 2026-09-06T12:56:39Z

Exact metadata: [source record](sources/issue-5356319949-ee643618723ae864db6ec981e7fe3601f2b6907c684af172030c119f96a45b2e.json).

Releasing movement while climbing should stop the climbing cycle and settle into idle. Releasing Sprint while still moving must not count as releasing movement.

**Status: The stop/rebind repair is source-only, and your latest test cannot grab walls at all.** Fix entry in #193 before asking you to test stopping mid-climb.

## comment 5550150311 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150311

Created: 2026-08-10T17:20:46Z; updated: 2026-08-10T17:20:46Z

Exact metadata: [source record](sources/comment-5550150311-4bfb40c1b4d17b88ec8b35828872b58b89bb8b8d6a4b336a210c8368affb6d02.json).

The release-edge climbing repair is installed. Releasing W/S/A/D or the stick now stops the outgoing movement task once instead of freezing that clip at animation speed 0, then selects the idle grip and records the postcondition. Test each direction, release during motion, then re-press; there must be no extra reach, frozen stride, A-pose, or stuck movement.

## comment 5550150336 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150336

Created: 2026-08-10T18:30:35Z; updated: 2026-08-10T18:30:35Z

Exact metadata: [source record](sources/comment-5550150336-260bb18c3e93b6cedd5878b45f7176f79fd8a23dfae277438420de7488ae477a.json).

Not fixed.

## comment 5550150354 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150354

Created: 2026-08-11T01:10:15Z; updated: 2026-08-11T01:10:15Z

Exact metadata: [source record](sources/comment-5550150354-c81181dbe0e33dfad0fda437e9de22dd5e60ce460781454a839b9812bccc45e3.json).

Same thing still. What do the logs say? Can you see his animation state/position?

## comment 5550150365 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150365

Created: 2026-08-11T01:46:02Z; updated: 2026-08-11T01:46:02Z

Exact metadata: [source record](sources/comment-5550150365-53201d88e6bce3eeae57c9d9bf2edd9a13ea1d9223b22453cdb8550ce66c14c9.json).

The release trace showed the outgoing climb animation still playing after the first stop request. Release now performs at most two bounded retries and rebinds the idle grip; it does not clear the task tree or stop every frame. Test releasing each movement direction and then pressing it again.

## comment 5550150379 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150379

Created: 2026-08-13T02:06:16Z; updated: 2026-08-13T02:06:16Z

Exact metadata: [source record](sources/comment-5550150379-696717b23a8f2f90f73a2d15db15a6455c940633c58a93c96669117ad9ed80b9.json).

**First real evidence for this issue — and it narrows the defect considerably.**

Climbing logging was silently disabled (see `fuckups.txt` entry 20), so every prior audit here was reasoning from an empty log. Now there are 4 complete release cycles:

```
release stop issued dict=...narrow_ledge_cliff@walk_left clip=move
release readback outgoingPlaying=0 idleSelected=0 idlePhase=0       anchorSpeed=0
release stop issued dict=mech_ladders@base clip=climb_up
release readback outgoingPlaying=0 idleSelected=1 idlePhase=0.01276 anchorSpeed=0
release stop issued dict=mech_ladders@base clip=climb_up
release readback outgoingPlaying=0 idleSelected=1 idlePhase=0.01344 anchorSpeed=0
release stop issued dict=mech_ladders@base clip=climb_down
release readback outgoingPlaying=0 idleSelected=0 idlePhase=0       anchorSpeed=0
```

Two things are now settled rather than assumed:

1. **The outgoing clip always stops.** `outgoingPlaying=0` on all four, and `anchorSpeed=0` every time — so he is not still travelling. The "continues the climb anim" symptom is **not** a failure to stop the clip, which is what the last two passes were built around.
2. **Idle selection fails half the time.** `idleSelected=0` with `idlePhase=0` on 2 of 4. The clip stops and nothing replaces it, which reads on screen as a frozen mid-stride pose rather than continued motion.

So the remaining defect is the *idle grip not being selected*, not the outgoing clip refusing to end. That's a different repair than the retry-the-stop logic currently in place.

The 2 failures are `narrow_ledge_cliff@walk_left` (lateral, Lexer-Lux/Lexeditor#253's path) and `climb_down`; the 2 successes are both `climb_up`. That's a small sample, but it points at the non-`climb_up` paths not having a valid idle to fall back to — which would also explain why sideways release looks worst.

Not fixing it on 4 samples and a guess about which idle each path should use. Next climb gives more cycles, and if the split holds along the same lines the fix is to give the lateral and descend paths their own idle selection rather than assuming the `climb_up` grip applies.

Leaving open.

## comment 5550150391 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150391

Created: 2026-08-14T06:08:34Z; updated: 2026-08-14T06:08:34Z

Exact metadata: [source record](sources/comment-5550150391-2a61f3632d1ad0f928ef2563eb8614e82100d1c9aab44bd5d33d53d00140695a.json).

**One of your two failing paths may need no fix at all — it may have no animation to begin with.**

The evidence here settled that the outgoing clip always stops (`outgoingPlaying=0`, `anchorSpeed=0` on all four cycles) and that the real defect is **idle selection failing**, 2 of 4. The split was:

- fails: `narrow_ledge_cliff@walk_left` (lateral) and `climb_down`
- succeeds: both `climb_up`

Working Lexer-Lux/Lexeditor#253 today I found something that changes how the first failure should be read. The lateral dictionary —

```
mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge_cliff@walk_left
```

— is **not attested anywhere**: not in the decompiled Story scripts, not in `DATA_MAP.md`. Unlike `mech_ladders@base` and `mech_climb@base@vertical@clamber_exits`, which both are. It has never been confirmed to exist in this build.

If it does not exist, `idleSelected=0` on that path is not an idle-selection bug at all — there is no dictionary to select an idle *from*, and `REQUEST_ANIM_DICT` on a missing name is a silent no-op. That would mean half your sample was measuring a missing asset rather than a logic fault, and building an idle-selection fix on it would have been fixing the wrong thing.

Both climb dictionaries are now checked with `DOES_ANIM_DICT_EXIST` once per session and reported outside the trace switch, since a missing animation asset is a defect rather than a diagnostic detail:

```
[climbing] anim dict present|MISSING role=sideways/ledge dict=…
```

Moving to `test me` because the next climb decides this without any further guesswork:

- ledge dict **MISSING** → that failure is explained; only `climb_down` needs its own idle, which is a much smaller and safer change than reworking selection for all paths.
- ledge dict **present** → the asset is real, both failures are genuine idle-selection faults, and the split-by-path theory from last time stands and can be fixed directly.

Climb a few times, including sideways and descending, then check those two lines together.


## comment 5550150402 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150402

Created: 2026-08-15T02:13:03Z; updated: 2026-08-15T02:13:03Z

Exact metadata: [source record](sources/comment-5550150402-f0a96f58b99a2971d9f48c8cc7a8e7168171084738ff798b94da7d6593183210.json).

The issue persists unchanged.

## comment 5550150418 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150418

Created: 2026-08-19T12:26:21Z; updated: 2026-08-19T12:26:21Z

Exact metadata: [source record](sources/comment-5550150418-9b69340085c83f2ef67ad196e7704967bb705c5c0e4c198a4496ead1f6f2a96f.json).

**The release stop can fail, and when it did the module said nothing at all.**

From Lexer's 2026-08-19 session:

```
release stop issued  dict=mech_loco_m@...@narrow_ledge_cliff@walk_left clip=move
release readback     outgoingPlaying=1 idleSelected=0
```

Every other release that session read `outgoingPlaying=0`, so the stop usually takes and occasionally does not — the outgoing clip keeps playing after the key is released, which is exactly the report.

**Two defects, and the second is why this issue had no evidence behind it:**

1. The audit retried twice and then cleared its pending flag and moved on. A clip that survived all three attempts kept playing **with no log line whatsoever**.
2. The readback itself was gated behind the `g_climbingTrace` flag, so in an ordinary session the whole audit was invisible. That is the `fuckups.txt` Lexer-Lux/Lexeditor#119 class: a diagnostic that is off by default protects nothing.

**Changes:**
- Retry budget raised from a magic `2` to `kClimbReleaseMaxRetries = 4`. The clip only has to lose one race and each attempt is nearly free.
- Exhausting the budget while the clip is still playing now logs, **ungated**:
  `release stop FAILED clip still playing dict=… clip=… retries=… stuckReleases=N`
- `stuckReleases` counts it, so the symptom is measured rather than inferred.

**Contract updated, not weakened.** It had pinned the literal `g_climbReleaseRetryCount < 2` — the magic number, not the requirement. It now requires a named constant, the failure report, the counter, and that the report is not trace-gated. Mutation-tested: removing the report or the counter both fail.

If `stuckReleases` is zero in the next session and the animation still continues, the cause is elsewhere and I will have said so rather than assumed this was it.


## comment 5550150427 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150427

Created: 2026-08-20T12:53:16Z; updated: 2026-08-20T12:53:16Z

Exact metadata: [source record](sources/comment-5550150427-94a064859b87bf99ef76a00fbb03b5fca64dfd069da9ec713e724258312b0ca4.json).

Returned test: releasing movement appears to produce one additional full animation cycle consistently. The required behavior is now explicit: the movement clip plays only while actual climb displacement occurs, and zero input or zero displacement must stop it or transition to idle immediately, with no queued extra cycle.

## comment 5550150441 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150441

Created: 2026-08-20T12:55:07Z; updated: 2026-08-20T12:55:07Z

Exact metadata: [source record](sources/comment-5550150441-38ca59d3f9d0f15db9095211434e51c213ea50b6ae9f9861b2981a3a49523ce4.json).

Important transition detail: releasing Shift and W together stops movement normally. Releasing Shift while W remains held causes an immediate animation hitch or cancellation. The next repair must test these as separate input transitions and must not treat loss of Shift as loss of all movement input.

## comment 5550150455 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550150455

Created: 2026-08-20T14:18:45Z; updated: 2026-08-20T14:18:45Z

Exact metadata: [source record](sources/comment-5550150455-7217de8cb9354958d9d3ef23728439478303960032c1d9eec810bb0694fd168e.json).

The extra cycle was a stop/rebind race. The module queued idle in the same update as the stop, while the outgoing clip could remain live for about 0.94 seconds; old retries could then stop a newly resumed clip with the same name. The source now waits for the outgoing clip to stop before binding idle, verifies that idle is playing, and cancels stale retries as soon as movement resumes. Releasing Shift while W remains held no longer counts as movement release. This is source-complete but not built or installed, so keep testing the current install until the next authorized build.

## comment 5550502696 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/251#issuecomment-5550502696

Created: 2026-09-05T08:11:15Z; updated: 2026-09-05T08:11:15Z

Exact metadata: [source record](sources/comment-5550502696-ad732e84064730778c5b05d7db7bc7146c711dcbf6b93ecc63a1d0c06ff99eb4.json).

blocked because jumping into walls just makes me jump now. no way to grab them so no way to test this.
