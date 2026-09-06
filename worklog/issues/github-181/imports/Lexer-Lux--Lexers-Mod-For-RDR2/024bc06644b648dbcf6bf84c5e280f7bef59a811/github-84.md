# GitHub issue #84 — binocular transition animation speed

## Failed layer probe

The installed `TASK::SET_ANIM_RATE` probe was tested on both candidate layers 0
and 2. Lexer observed no speed difference. The unified log later showed a
configured rate of 10 was clamped to 4 and still took roughly normal draw/stow
times. The engine-owned binocular swap task therefore did not respond to the
layer-wide native. That probe was removed rather than represented as a feature.

## Narrow authored-clip implementation

The complete shipped animation index identifies the exact fallback dictionaries
and clips that static research had previously missed:

- `mech_inventory@equip@fallback@base@unarmed@satchel@binoculars`
- its standing `_gesture` variant;
- `mech_inventory@equip@fallback@crouch@unarmed@satchel@binoculars`
- its crouched `_gesture` variant;
- clip `unholster` for draw and `holster` for stow.

The transition now applies `_SET_ENTITY_ANIM_SPEED`
(`0xEAA885BA3CEA4E4A`) to those exact candidates only while the native swap is
running, then restores 1.0 on scope entry, stow completion, timeout, disable,
death/fade, or abort. Inactive dict/clip pairs are harmless no-ops. The log
records the exact matched dictionary/clip and elapsed time. The failed
`TransitionAnimLayer` option was removed; `TransitionAnimRate` remains the
hot-reloaded multiplier.

## In-game acceptance

With `TransitionAnimRate` above 1.0, test standing and crouched draw/stow. The
authored hand/satchel/binocular motion should be visibly faster while movement
and the scoped idle remain normal. The unified log must name a matched dict; an
`unobserved` result means this narrower fallback still did not own the live clip
and must not be called complete.

## 2026-08-10 returned actionable: live target was a clipset, not an animation dictionary

The installed log answered the previous implementation conclusively. At a
configured value of 10 (clamped to 4), every tested draw and stow completed with
`dict=unobserved`; representative draw/stow elapsed times remained about
1047/906 ms. The setting was `TransitionAnimRate`, but it had no visible effect
because the code passed `mech_inventory@equip@fallback...` CLIPSET records to an
entity-animation native as if they were active animation dictionaries.

The bounded repair removed those disproven targets. The project animation
index `_downloads/rdr3_discoveries/animations/megadictanims/megadictanims.lua`
identifies the real binocular animation dictionaries used while raising and
lowering the binoculars:

- standing and crouched `mech_weapons_special@binoculars@...@intro@sweep`
  dictionaries with `aim_0`, `aim_l/r90`, and `aim_l/r180` clips;
- matching `...@outro@sweep` dictionaries with `aim_med_0/l90/r90_outro`.

During only the bounded draw/stow state, the module now tests those exact pairs
with `IS_ENTITY_PLAYING_ANIM(..., 1)`, the same predicate flag used by shipped
Story scripts. `_SET_ENTITY_ANIM_SPEED` is called only for a pair proven active
on Arthur, and the exact dictionary and clip are logged and restored to 1.0.
The draw observer stays armed past the inventory swap edge because forced aim
starts the authored binocular intro after that swap; the old code restored the
rate on the same forced-aim frame before the intro could be observed.

The next integrated runtime must show `observed=1` with an exact
`mech_weapons_special` dictionary/clip and a visibly faster authored
raise/lower in both standing and crouched tests. If it remains `unobserved`, the
animation-index mechanism is disproven too; build success is not acceptance.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- Earlier logs said the setting was active even though every target animation dictionary was `unobserved`; a setter call against a nonexistent live clip was not success.
- The replacement mutates speed only after an exact indexed binocular intro/outro pair is positively observed, logs dict/clip/readback, and restores 1.0. It remains failed unless the log shows `observed=1` and the transition is visibly faster.

## 2026-08-10 recurrence audit before the latest transition-rate repair

- **Primary evidence/reference:** Lexer reports that the transition remains
  vanilla-slow and now asks how to turn the rate up. The setting is
  `TransitionAnimRate`; prior logs proved the first clipset targets were never
  observed. The current candidate's exact `mech_weapons_special` dictionary and
  clip strings must be checked against the supplied local animation index and
  the installed log before any further target is accepted.
- **Sanctioned path:** mutate speed only for an exact animation dictionary/clip
  positively active on Arthur during the authored intro/outro, then restore
  1.0 on every exit. If no indexed pair is observed, keep the result explicitly
  failed rather than widening to a layer/global animation-rate fight. The
  player-facing setting must be read/hot-reloaded at a documented cadence and
  its actual effective value must be visible in the log.
- **Execution proof:** for every draw and stow, record requested/effective rate,
  phase, elapsed time, every bounded observation result, the exact matched
  dictionary/clip if any, speed-set attempt, postcondition available from the
  animation state, restoration, and an idle heartbeat. `observed=0` or an
  unmatched setter is failure.
- **Player-visible acceptance:** changing `TransitionAnimRate` to a clearly high
  value through the documented setting makes standing and crouched authored
  pull-out/put-away visibly faster while locomotion, the raised idle, optics,
  mask, prompt behavior, and native satchel presentation remain normal.
- **Every per-frame native:** `IS_ENTITY_PLAYING_ANIM` may run only while a
  bounded draw/stow observer is armed and only across the resolved finite pair
  table. `_SET_ENTITY_ANIM_SPEED` may run only after a positive active-clip
  readback and once again to restore. No per-frame setter during the raised idle
  and no unbounded dictionary probing are allowed.

## Returned-test correction: Rockstar's actual binocular state dictionary

The `mech_weapons_special` replacement was still the wrong ownership claim.
Rockstar's Story script assigns `Local_0.f_3 = "mech_inventory@binoculars"` at
`_downloads/RDR2-Decompiled-Scripts/script_rel/binoculars.c:25`. The complete
in-game animation index resolves that exact dictionary with player clips
`enter_2_hold` and `hold_2_exit` (and separate prop clips). The generic aim
sweep table was removed rather than tuned again.

The bounded transition observer now checks only the exact Story-owned player
clip for the current phase every 25 ms. It calls `_SET_ENTITY_ANIM_SPEED` once,
only after `IS_ENTITY_PLAYING_ANIM(..., 1)` positively observes that pair, and
polls only the matched pair until completion. The restore call is issued once
only if a mutation actually happened. This removed the previous per-frame
setter and the bug where several blended pairs could be mutated while only the
first was restored.

`TransitionAnimRate` is now read directly from the INI at each draw/stow start,
then clamped to the supported existing 1.0-4.0 range. The log reports both the
requested and effective value, the exact pair, positive playing readback,
setter count, elapsed time and restore count. Thus the current configured `10`
is explicitly reported as effective `4`, and changing the key applies on the
next binocular transition without an ASI restart.

Static verification was assigned to
`tools/reverse-engineering/verify_binocular_transition_probe_issue_84.py`.
Runtime acceptance remains required: both standing and crouched draw/stow must
log the exact `mech_inventory@binoculars` clip with `observed=1`, `mutated=1`,
one apply and one restore, and the authored motion must be visibly faster. If
the exact player clip remains unobserved or the visible speed is unchanged, the
issue remains failed; no global/layer fallback was added.

## 2026-09-06 — Lexeditor #181 retirement candidate

Read the current Lexeditor #181 body and archived conversation, fuckups.txt,
combat_inventory.cpp, script.cpp and the generated menu model before editing.
The latest explicit acceptance permits removing the ineffective control.
Primary evidence: the module's beginTransitionRate clamps the stored 10 to 4;
no player-visible improvement is confirmed. The generated menu calls this
multiplier points/s. Recurrence risks: treating setter/readback logs as measured
animation speed (classes 1/2), stale controls surviving removal (class 5), and
calling source-only work installed (classes 4/5).

Chosen path: remove the rate observer, all animation-speed setter calls belonging
to it, config reader/default and generated control. Preserve the native draw,
put-away, hold/latch, ownership and camera-readiness paths. No new native,
constant, animation, task-layer guess, or advertised speed is introduced.
Execution proof required: regression verifies absence and retained paths; build
and in-game behavior are separate. #357 remains unresolved; this is not evidence
that the animation-speed observer caused the reported crash.

Validation: the seven retirement checks pass; generated header reproduction
matches the matching runtime schema byte-for-byte. Only the retired row, total
count and digest change in that header. No unrelated menu ranges/types change.
ASI build/install and gameplay acceptance remain outstanding.
