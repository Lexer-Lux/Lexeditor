# GitHub #161 - sideways climbing execution

## 2026-08-10 corrected asset binding; rejected fallback removed

The returned runtime result proved the preceding fallback design unacceptable:
it restored the exact Story clip Lexer had already identified as the
horse-leading animation. The asset inventory also disproved the premise behind
that fallback. `walk_left` is not a clip within the parent `narrow_ledge`
dictionary. It is the final component of the complete dictionary name:

`mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge@walk_left`

That dictionary's listed traversal clip is `move`. The prior implementation
requested the truncated parent dictionary and a nonexistent `walk_left` clip,
so its timeout inevitably selected the rejected Story animation.

The runtime now requests the complete authored dictionary and plays `move`.
The Story dictionary/clip, automatic fallback state, configuration switch, INI
key, and both settings-menu entries were removed. A delayed or failed load now
logs `fallback=none`; it cannot silently change the requested animation.

The #161 verifier reads the shipped animation inventory, requires this exact
dictionary/clip pair, and rejects the horse-leading Story strings or fallback
setting anywhere in runtime/config/UI. #159, #160, #97, prone/climb parity,
#6, generated settings parity, settings-page, and lifecycle checks passed.
Runtime still must prove the authored clip visibly traverses left/right,
reverses, and stops on release; static evidence is not visual acceptance.

Development build `452E859A92906B226EDF26F5C31EC07D81F5783E067311F746623A830927B3B8`
compiled successfully. RDR2 was still running, so the loaded ASI was not
overwritten. The standard hash-verifying installer is waiting in the background
and will install this build only after that process exits. #161 remains
`actionable` until that install is read back; it must not be called `test me`
from compilation alone.

## 2026-08-10 returned horse-leading regression audit before source repair

Lexer immediately observed the same horse-leading/dancing animation that had
already been rejected many attempts earlier. The source knowingly described
`cliff_p1_walk_loop_player` as reading like dancing or leading a horse, then
automatically selected it whenever the promised narrow-ledge path failed. This
was not an acceptable fallback and must not remain configurable or automatic.

The underlying narrow-ledge failure was a concrete asset-addressing error.
`rdr3_discoveries/animations/ingameanims/ingameanims_list.lua` identifies
`mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge@walk_left` as the
dictionary and lists its playable clips, including `move`. The implementation
instead treated `walk_left` as the clip and requested the nonexistent parent
dictionary ending at `@narrow_ledge`. Its 600 ms failure therefore guaranteed
the rejected Story fallback. The correction must use the complete dictionary
plus `move`, remove the Story fallback and setting, and reject any verifier that
still requires `cliff_p1_walk_loop_player`.

## Recurrence audit before source repair

### Primary evidence

- The live issue says repeated prior `test me` transitions produced no
  sideways climbing. #97's latest live comment repeats "Sideways climbing
  still gone."
- The latest installed unified log contains no climbing record despite the
  installed trace setting being enabled. It cannot prove which lateral branch
  executed in the reported earlier session; the evidence was overwritten on
  the next launch. This repair therefore preserves the failure with bounded
  execution/readback diagnostics instead of claiming a runtime branch result.
- The string corpus proves the locomotion set and full entries exist:
  `ArchiveItems.txt:2810270-2810276` contains the narrow-ledge `idle_left` and
  `walk_left` strings. It does not prove that the set is streamable as a raw
  `TASK_PLAY_ANIM` dictionary.
- Current code has no escape from that distinction. With the default setting it
  repeatedly requests the narrow-ledge dictionary; while it is not loaded it
  resets `g_climbAnimClip` and `g_climbLastAnim` every update. Consequently
  `motionAnimBound` never becomes true and `motionGain` remains zero forever.
  The shipped story-side `script_story@fus1@ig@ig_1_cliffsidetraverse /
  cliff_p1_walk_loop_player` task is the already-known executable lateral
  fallback, although its pose is less ideal.

### Sanctioned path and execution proof

Attempt Arthur's narrow-ledge clip first. If its dictionary does not load, or
the issued clip never progresses, switch once to the known Story lateral clip
instead of multiplying lateral movement by zero forever. Record selected path,
dictionary loaded state, clip phase, input direction, motion gain, commanded
anchor travel and actual entity travel. No timeout may be reported as proof
that an animation bound.

### Player-visible acceptance

While attached, A/D or the left stick must visibly move Arthur in both surface
tangent directions and play a progressing lateral animation. Direction reversal
must reverse traversal. Releasing input must stop under #159. There must be no
static-pose sliding, zero-distance "success," repeated task restart, A-pose,
or loss of surface ownership.

### Per-frame native inventory

No new per-frame graph writer is added. The existing issue-on-change
`TASK_PLAY_ANIM` and direction-specific animation-speed scalar remain. The new
fallback decision is state/readback driven. Lateral movement continues through
the existing custom-climb coordinate owner only after a selected clip has had a
bounded bind window; diagnostics are rate-limited.

## Implemented repair and static result

Each attachment now attempts the shipped narrow-ledge dictionary once. If it
does not load within 600 ms, or `walk_left` neither progresses nor reports
playing 450 ms after issuance, the state selects the already-streamed Story
cliff-traverse clip. The lateral gain no longer treats a 160 ms timeout as proof
that the unverified narrow-ledge task bound; vertical ladder motion retains its
existing bounded allowance. Direction changes do not restart the failed
dictionary wait.

Every 900 ms of held lateral input records direction, chosen path,
dictionary/clip, phase, gain, commanded anchor travel and actual entity travel;
zero phase or less than 0.05 m is a warning, not success. A five-second climbing
heartbeat now distinguishes idle/not-executed from an executed traversal.

`verify_climbing_issue_161.py` passes, together with #97, prone/climb parity,
#6 and the human movement checks. Runtime must still prove both A/D directions,
animation quality of whichever path executes, reversal and release. The Story
fallback is executable but previously judged less visually suitable, so its
activation will remain visible in the log rather than being described as the
preferred final pose.

## 2026-08-10 live pose rejection

The log proved the generic `narrow_ledge@walk_left / move` task was loaded,
playing, and moving the anchor about 0.85-0.99 m. Lexer saw the actual result:
Arthur stood with his arms down and walked or slid sideways. Therefore those
readbacks prove execution only, not a climbing pose.

The authored inventory also contains the more specific
`narrow_ledge_cliff@walk_left / move` dictionary. The lateral path now uses that
cliff-specific asset. The rejected `script_story` horse-leading fallback remains
absent. Runtime must still prove the cliff variant keeps hands on the surface;
its name and playing readback are not visual acceptance.
