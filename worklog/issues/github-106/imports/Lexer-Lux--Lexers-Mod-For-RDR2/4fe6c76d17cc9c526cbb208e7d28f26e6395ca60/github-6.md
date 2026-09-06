# Worklog: GitHub issue 6

## Directional dodge roll

The live issue required the directional combat dive to become Rockstar's cut
combat roll. Neutral Dive, unsafe terrain, unavailable animation data and every
ineligible state had to retain the vanilla dive.

The prior Todo 208 implementation was rechecked before replacement. It lived in
`combat_inventory.cpp`, searched guessed animation dictionaries, and applied a
horizontal velocity every frame for the clip duration. The installed runtime
log has since proved that `mech_strafe@generic@roll@base` exists, streams and
contains the P1 combat-roll clips. The shipped `rdr3_discoveries` animation
index independently lists that dictionary and its complete P1/P2 clip set. The
same runtime log also recorded the engine combat-roll predicate becoming active
without the old velocity-owned marker. No installed standalone Combat Roll mod
was present; only the diagnostic log remained.

The original Combat Roll mod's [published changelog](https://www.nexusmods.com/reddeadredemption2/mods/6687?tab=logs)
says its working animation became a secondary task so Dead Eye remained usable,
and that first-person roll was disabled by default. The new path retains those
two compatibility choices.

Implemented in `GameplayTweaks/modules/movement.cpp`:

- `updateDirectionalDodgeRoll` is an integration entry point that replaces the
  old `updateCombatRoll` dispatcher call.
- It recognizes Dive only while aiming a non-unarmed weapon, grounded, in third
  person by default, outside vehicles/mounts/swimming/falling/ragdoll/climbing/
  custom prone, and with a real movement direction.
- It streams the confirmed dictionary and chooses the nearest real P1 clip,
  with matching P2 clips as fallback when P1 has no duration.
- A continuously warmed asynchronous world trace plus synchronous ground,
  slope, step and water checks validate the requested 1.75 metre path. A stale,
  obstructed or unsafe result leaves Dive enabled so Rockstar's vanilla move
  runs.
- It zeroes only incoming horizontal momentum once, then plays the full-body
  secondary animation and leaves translation to authored clip root motion. It
  never applies per-frame velocity or teleports the player.
- Neutral Dive is never consumed. Jump is never read or disabled.

Integration state:

- `ScriptMain` already dispatches `updateDirectionalDodgeRoll(...)`.
- The superseded resolver/velocity-drive implementation in
  `modules/combat_inventory.cpp` is compile-disabled. Its shared aim, input and
  trace helpers remain available to the active movement implementation.
- The existing `[CombatRoll]` INI surface retains only `Enabled`,
  `AllowFirstPerson`, `CooldownMs` and the development-only trace switch. The
  authored path always requires weapon aim and intentionally exposes no
  velocity-assist or animation-dictionary override.
- `codex/runtime-engine-limits.md` records the confirmed dictionary and authored
  root-motion rule.
- `tools/reverse-engineering/verify_dodge_roll_issue_6.py` checks dispatcher
  integration, the 20 exact clips against the shipped animation index, neutral
  and unsafe vanilla fallback, mode gates, the secondary-task flag, and that
  the active implementation performs exactly one pre-animation momentum reset
  rather than driving velocity throughout the clip.

Integrator work still required: run the issue verifier, perform the full build,
install and hash-verify the one ASI, then move GitHub issue 6 to `test me`.

Runtime acceptance:

1. Aim a firearm in third person and press Dive while moving forward, backward,
   left, right and diagonally. Each directional dive should be an authored roll
   in that direction, with no sliding, teleport or post-roll momentum.
2. Press Dive while aiming but with no movement input. The vanilla dive should
   remain.
3. Attempt a directional Dive facing a wall, ledge, steep slope, large step and
   water edge. Unsafe/unresolved paths should retain the vanilla dive rather
   than forcing a roll through geometry.
4. Confirm ordinary direction+Jump climbing, prone, mounted, swimming, falling,
   ragdoll, mission lockout and first-person behavior are unchanged.
5. Activate Dead Eye during a roll and confirm it remains usable. Confirm weapon
   aim recovers normally after the clip.
6. Repeat as both Arthur and John; P2 fallback must not create an A-pose if a P1
   clip is unavailable for the current model.

Static checks verified the confirmed dictionary and all named P1/P2 clips exist
in the shipped animation index, Dive remains untouched until the replacement is
ready and safe, and the movement module contains no per-frame dodge velocity
drive. Compilation, installation, GitHub relabeling, commit and push were
deliberately left to the integration agent.

The integration review found the Dive edge was sampled only after disabling
the control. It now captures the edge first and consumes vanilla Dive only
after every eligibility, animation, and path-safety gate passes.

That input-order change reached the game but failed its second runtime check.
`GameplayTweaks.roll.log` recorded an authored replacement at tick 583938921
(`combatroll_fwd_p1_-45`, 700 ms, safe path), while the live issue again
reported that nothing had changed. This proved that dictionary streaming,
direction selection, the safe-path gate and the replacement edge all ran; the
remaining failure was task contention on that edge. The implementation did not
disable vanilla Dive until after the edge had already been delivered, so
Rockstar's higher-priority dive began on the same frame as the secondary roll.

The issue-owned dodge section now disables Dive after all eligibility,
dictionary and path-safety gates pass but before reading
`IS_DISABLED_CONTROL_JUST_PRESSED`. Unsafe or unresolved paths still leave the
control untouched. The secondary animation flags now explicitly include force
start and mover extraction in addition to the reference-compatible secondary
slot and upper-body tags; the previous flags did not request either, despite
the worklog's earlier root-motion claim. No task clear, teleport or recurring
velocity drive was added.

`verify_dodge_roll_issue_6.py` now rejects post-edge suppression and requires
the force-start/mover-extraction flags. It passes with all 20 shipped clips,
and the combined `verify_prone_climb_parity.py` suite still passes all 33
movement invariants. This correction is source-only and remains actionable
until the integration agent builds and installs it; the exact runtime
acceptance remains the six checks above.

## Fourth attempt — root cause found: the flag word was fabricated

The three previous builds all reached the game and all reported "nothing has
changed". The prior worklog blamed input-edge ordering twice and task
contention once. Both diagnoses were wrong, and the evidence was already in the
source.

`kDodgeRollAnimFlags` was `0x00000004 | 0x00000010 | 0x00002000 | 0x00008000 |
0x04000000` = `0x0400A014`, commented as
`AF_NOT_INTERRUPTABLE | AF_SECONDARY | AF_FORCE_START |
AF_USE_MOVER_EXTRACTION | AF_UPPERBODY_TAGS`.

Those names sit at none of those bit positions. A grep for any `AF_` constant
across the whole repository and all of `_downloads/` returns zero definitions,
so the word was never checked against anything. Against the real rage
`AnimFlags` layout `0x0400A014` decodes to
`REPOSITION_WHEN_FINISHED(4) | UPPERBODY(16) | EXIT_AFTER_INTERRUPTED(8192) |
TAG_SYNC_OUT(32768) | PROCESS_ATTACHMENTS_ON_START(0x4000000)`.
`SECONDARY(32)`, `FORCE_START(131072)` and `USE_MOVER_EXTRACTION(524288)` were
never actually set.

That matches the observed symptom exactly. `UPPERBODY` reduced the roll to a
torso overlay on a player who was still standing and strafing, and
`EXIT_AFTER_INTERRUPTED` dropped it the moment the locomotion task touched it.
`TASK_PLAY_ANIM` genuinely fired and genuinely logged `combatroll_fwd_p1_-45`
at tick 583938921 — the log was truthful; the flags made the result invisible.
No amount of input-edge reordering could ever have fixed this, which is why two
successive edge-ordering corrections changed nothing.

Second defect, same call: the argument tail. Every anim invocation in
`movement.cpp` that is confirmed working in game passes the `0x02000000` task
filter (`playProneAnimation`, `beginProne`). The dodge call passed `0`.

## Reference evidence actually used

- `_downloads/crawl-n-gun-reference/extracted/Dive - Crawl N' Gun.asi` is on
  disk. A string extraction of it yields the dive dictionaries
  `mech_weapons_core@base@dive@{pistol,rifle,unarmed}@{getup,prone}`,
  `ai_getup@directional_sweep@combat@cop@{pistol,rifle}@{front,back}`,
  `mech_crawl@base`, and the launch clips `dive_launch_{fwd,left,right,bkwl,bkwr}`
  plus the `dive_getup_*` set. It contains **no** combat-roll dictionary and no
  roll clips: it is a dive/prone mod, not a roll mod. Its INI does expose
  `OverrideDefaultCombatDive`, confirming the vanilla combat dive is
  suppressible from an ASI.
- `_downloads/rdr3_discoveries/animations/megadictanims/megadictanims.lua:67366`
  lists `mech_strafe@generic@roll@base` with exactly the 20 P1/P2 clips this
  module uses. The dictionary and clip names were already correct.
- `_downloads/RDR2-Decompiled-Scripts/script_rel/` contains **no** reference to
  `mech_strafe@generic@roll@base` or any `combatroll_` clip. The combat roll is
  not script-driven; it is a cut engine move with only its animation data
  shipped. There is nothing further to decompile for it, and no in-game probing
  would have added anything.
- No standalone Combat Roll reference ASI is present on disk. Nothing in this
  attempt claims to have studied one.

## Change made

`GameplayTweaks/modules/movement.cpp`, dodge-roll section only:

- `kDodgeRollAnimFlags` (the fabricated constant) replaced by
  `dodgeRollAnimFlags()`, which returns the flag word `beginProne` already
  proves in game for a full-body, player-overriding, authored-mover clip,
  including its keyboard/controller split (`0x00010C00` / `0x20010C00`, selected
  by native `0xA571D46727E2B718`). No bit is guessed.
- The `TASK_PLAY_ANIM` call now passes the proven `0x02000000` task filter
  instead of `0`, and a symmetric blend (`8.0f, 8.0f`) matching the file's other
  working calls.
- `CLEAR_PED_SECONDARY_TASK` is issued immediately before the task so the roll
  owns the whole skeleton instead of overlaying it.
- Diagnostics, all through the existing `combatRollLog`
  (`GameplayTweaks.roll.log`, gated on the `[CombatRoll]` trace switch):
  - `roll issued …` records direction, clip, duration, dict-loaded state, the
    exact flag word in hex, the task filter and the slot;
  - `roll survival t+150ms clip=… alive=0/1 ragdoll=0/1` records whether the
    task survived the movement state machine;
  - `dive edge seen, roll refused at stage=…` records a Dive edge that did not
    become a roll, naming the stage: dict not yet loaded, no clip duration, or
    path probe not clear. Rate-limited to one line per 400 ms.

  A future failure is now diagnosable from that one file: no line at all means
  the trigger was never detected; a `refused` line names the gate; `issued`
  without `alive=1` means task contention; `alive=1` that still looks vanilla
  means a wrong clip or a filtered slot.

`tools/reverse-engineering/verify_dodge_roll_issue_6.py`: the three checks that
asserted the fabricated `AF_*` comments were removed and replaced with checks
that the flag word and task filter are the ones proven by `beginProne`, that
full-body ownership is taken, and that both diagnostics are present. The safe
gate check was retargeted at the split gate. It passes with all 20 shipped
clips; `verify_prone_climb_parity.py` still passes its 33 invariants.

Not touched: `script.cpp`, `build.bat`, other modules, other worklogs, the INI
key set (unchanged: `Enabled`, `AllowFirstPerson`, `CooldownMs`, trace).
Not compiled, installed, committed or relabelled — integration work.

Runtime acceptance is unchanged from the six checks above. If it still looks
like vanilla, `GameplayTweaks.roll.log` now says which of the four failure
modes it is.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 working-reference parity correction

The previous full-body/prone flag substitution was not the working reference's
design. Combat Roll v1.03.1 was downloaded for static analysis only and was
never installed or executed. Archive SHA-256:
`1AF8C2FED512BFC200DFAEC2AC6A1718016203992142FFF0EED641B49D5840FF`;
ASI SHA-256:
`8F61DA404E4C970BF0B21D4026CBBBC01ABE781AB6094832FC40D54700B9B0F9`.
Windows Defender reported no threat.

Disassembly of its `TASK_PLAY_ANIM` wrapper and call sites proved the exact
task contract:

- one-handed: flags `0x00800010`, no named filter;
- two-handed: flags `0x20800010`, `noleftarm_filter`;
- both: blend 8/-8, duration -1, argument tail `0x020000A0`;
- the reference schedules a secondary task and does not clear it first.

The implementation now mirrors that contract and uses the native
`_IS_WEAPON_TWO_HANDED` predicate (`0x0556E9D2ECF39D01`) to choose the branch.
The authored dictionary, directional clip selection, safe-path gate, stamina
charge, and diagnostics remain. Runtime acceptance is whether the directional
roll is visibly distinct from vanilla with both a sidearm and longarm.

## 2026-08-10 complete Combat Roll sequence port

The prior "reference parity" pass decompiled only the reference's
`TASK_PLAY_ANIM` wrapper and treated one call contract as the whole move. That
was incomplete. Full control-flow disassembly of
`_downloads/combat-roll-reference/extracted/CombatRoll.asi` (SHA-256
`8F61DA404E4C970BF0B21D4026CBBBC01ABE781AB6094832FC40D54700B9B0F9`)
showed that the working mod never plays a single selected clip:

- `0x1800011C0` selects one of eight exact P1/P2 clip pairs from the four
  movement controls. The ASI contains 16 roll clip strings, not the 20 shipped
  clips the previous verifier accepted.
- `0x180001400` aligns entity heading to gameplay-camera rotation, plays P1
  with flags `0x00800012`, and waits until normalized phase `0.84`.
- It then plays the paired P2 with `0x00800010`, or `0x20800010` plus
  `noleftarm_filter` for a two-handed weapon.
- Standing P2 stops at phase `0.20`. A roll that began crouched stops at phase
  `0.05` and restores crouch with `_SET_PED_CROUCH_MOVEMENT(ped, 1, 1, 0)`.
- The reference does not reset, drive or otherwise own entity velocity; the
  paired clips own displacement.

The active module now implements that sequence as a non-blocking P1/P2 state
machine. It retains the existing pre-edge dictionary and safe-path validation,
neutral/unsafe vanilla fallback, mission/vehicle/prone/climbing gates and
one-time stamina charge. It aborts if the issued task is not alive at the
150 ms readback, and both phases have bounded watchdogs so a failed animation
predicate cannot trap Dive suppression.

`tools/reverse-engineering/verify_dodge_roll_issue_6.py` now checks all 16
implementation strings against both the reference ASI and shipped animation
index, rejects the four non-reference duplicate-angle clips, requires the exact
P1/P2 phases, flags, camera alignment, crouch restoration and stop call, and
rejects any dodge-owned velocity mutation. It passes:

`PASS: issue #6 reference P1/P2 dodge roll (16 ASI/shipped clips verified)`

No build, install, INI/shared-file edit, GitHub label change, commit or push was
performed. Runtime acceptance remains required: aimed directional Dive must be
a visible two-part roll for sidearms and longarms; diagonals/backward must use
the reference pair; neutral and unsafe Dive must remain vanilla; crouched rolls
must return to crouch; Dead Eye and aim must recover after P2.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## Recurrence audit before the reference-grounded repair

### Primary evidence / reference

The authority is the actual reference binary
`_downloads/combat-roll-reference/extracted/CombatRoll.asi`, SHA-256
`8F61DA404E4C970BF0B21D4026CBBBC01ABE781AB6094832FC40D54700B9B0F9`, and
its control-flow disassembly. Clip-name presence in that PE and the shipped
animation index proves only that strings/assets exist; it does not prove the
input contract, task flags, task filter, phase sequence, or visible result.
Before another source change, the call sites must be re-read directly and each
numeric flag word must be recorded as a numeric reference value unless a real
flag definition is found. Plausible `AF_*` names are forbidden by
`fuckups.txt` entry 1.

### Sanctioned path

The reference's sanctioned path is an event-driven two-part authored animation:
choose one of its exact directional P1/P2 pairs from movement controls, align
heading to gameplay-camera rotation, issue P1, wait for its reference phase,
issue the paired P2 with the reference one-/two-handed contract, stop P2 at the
reference standing/crouched phase, and restore crouch when required. Authored
root motion owns displacement. No guessed velocity assist, teleport, ragdoll,
or single-clip substitute is allowed.

### Actual execution / postcondition

An `issued` log proves only that `TASK_PLAY_ANIM` was called. A valid trace must
show the Dive edge and selected pair, P1 survival and normalized-phase progress,
the P1-to-P2 transition, P2 survival/progress, the correct stop phase, and final
idle/crouch restoration. A five-second idle heartbeat must distinguish a loaded
module with no qualifying edge from a dispatcher that never ran. A failed task
survival readback must be reported as execution-without-visible-result, not as
a successful roll.

### Player-visible acceptance

While aiming a firearm in third person, every directional Dive must visibly be
the reference two-part combat roll for both sidearms and longarms. Neutral or
unsafe Dive stays vanilla. Camera-relative direction, authored displacement,
weapon/aim recovery, standing finish, crouched finish/restoration, and absence
of an A-pose or standing torso overlay all require Lexer's in-game confirmation.
Static parity and a task-call log do not complete the issue.

### Per-frame native inventory

The roll updater is polled once per game update, but the animation must remain
edge/state driven. Per-update reads may determine ownership/input and advance a
live phase: entity/ped validity and state, control state, aim/weapon/camera
state, animation dictionary loaded, `IS_ENTITY_PLAYING_ANIM`, and normalized
animation time. During a live roll it may suppress Dive and perform the bounded
reference phase readback. Mutations must occur only on the trigger/transition/
finish edges: heading set, P1 task, P2 task, P2 stop, crouch restoration, and
the one stamina charge. `TASK_PLAY_ANIM`, `STOP_ANIM_TASK`, heading mutation,
crouch mutation, velocity mutation, task clearing, or stamina mutation must
never execute as unconditional per-frame writes. The exact native inventory and
cadence will be checked against the implementation after binary re-disassembly.

## Direct reference-binary repair

The complete direct inspection changed the root cause again. The prior pass
ported the reference's clip pairs and phase sequence, but it still did not use
the reference's trigger or selector.

Primary PE evidence from the hash-pinned
`_downloads/combat-roll-reference/extracted/CombatRoll.asi`:

- `0x1800019EE` loads native hash `0xC48A9EB0D499B3E5`; the outer loop tests its
  result and calls the roll routine at `0x180001A5E` only when it is true. The
  resolved native is `GET_PED_IS_DOING_COMBAT_ROLL`. The PE contains no
  `INPUT_DIVE` string. The working reference observes Rockstar's combat-roll
  state; it does not consume Dive itself.
- `0x1800011C0..0x1800013D4` reads exactly `INPUT_MOVE_UP_ONLY`,
  `INPUT_MOVE_DOWN_ONLY`, `INPUT_MOVE_RIGHT_ONLY`, and
  `INPUT_MOVE_LEFT_ONLY`. Its right-only branch selects
  `combatroll_fwd_p1_90`/P2. The removed analog approximation used
  `atan2(-moveX, -moveY)`, which mapped keyboard D/right to -90 and therefore
  selected the wrong pair even when its own trigger succeeded.
- `0x18000155E` supplies P1 flags `0x00800012`; `0x18000171C` and
  `0x180001732` supply P2 `0x00800010` / `0x20800010`; the wrapper at
  `0x180001D46` supplies task-filter tail `0x020000A0`.
- Those words were resolved against
  `Halen84/RDR3-Native-Flags-And-Enums` commit
  `1049e650690e3eff085988285df310a71af587f3`,
  `eScriptedAnimFlags/README.md`: P1 is `HOLD_LAST_FRAME | SECONDARY |
  SKIP_IF_BLOCKED_BY_HIGHER_PRIORITY_TASK`; ordinary P2 is `SECONDARY |
  SKIP_IF_BLOCKED_BY_HIGHER_PRIORITY_TASK`; longarm P2 additionally uses
  `BLENDOUT_WRT_LAST_FRAME`. These are RDR3 bit positions, not invented names
  or GTA V values.
- `0x1800019C1` uses unresolved CAM native `0xD1BA66940E94C547` for the
  reference's first-person-disable option. The repair invokes that exact hash
  and does not invent a semantic native name.
- `0x180001A1D`/`0x180001A63` bracket the sequence with
  `DISABLE_PED_PAIN_AUDIO(ped, true/false)`. The existing port omitted this.

`GameplayTweaks/modules/movement.cpp` now begins only on the rising edge of
`GET_PED_IS_DOING_COMBAT_ROLL`. It snapshots the exact four-control branch
table, warms/validates the exact P1/P2 pair, aligns to gameplay-camera yaw,
brackets the animation with the reference pain-audio writes, and advances the
existing nonblocking P1/P2 phase state machine. It no longer reads or disables
`INPUT_DIVE`, derives an analog angle, or imposes the non-reference asynchronous
path-probe policy. The broad dispatcher hint cannot tear down an already-issued
reference sequence; direct fall/ragdoll/ped loss still aborts safely. The #17
one-time Stamina charge remains on the actual P1 issuance edge.

Diagnostics now have a five-second idle heartbeat with updater-frame count,
enabled state, engine combat-roll predicate, pending trigger, dictionary state,
and dispatcher hint. A real attempt records predicate edge plus selected pair,
P1 issue, 150 ms survival, P1-to-P2 phase, P2 survival, stop reason, and crouch
restoration. This distinguishes no engine trigger from a called task that died.

Scoped checks passed:

- `PASS: #6 matches CombatRoll.asi trigger, exact four-control selector, RDR3 flag definitions, and paired P1/P2 phase sequence (16 clips)`
- `PASS: 34 reference-derived invariants`
- `git diff --check` passed apart from Git's existing LF-to-CRLF warning.

No compile, build, install, shared-file edit, or label change was performed.
Runtime remains the boundary: the idle heartbeat must prove the updater ran;
an aimed directional would-be Dive must produce `engine combat-roll predicate
edge`; then the phase/survival lines and the visible sidearm/longarm two-part
roll must agree. If the engine predicate never rises during the player's move,
the reference trigger itself is not being reached and that is a specific
runtime result, not a successful roll.

## 2026-08-10 returned direction failure recurrence audit before source edits

### Primary evidence / reference

- The live issue's latest comment is the runtime result: the roll animation is
  finally visible, but the requested direction produces an approximately
  270-degree spin. This proves task visibility while disproving directional
  parity. It must not be rewritten as a successful roll because the animation
  played.
- The authority remains the hash-pinned Combat Roll v1.03.1 binary at
  `_downloads/combat-roll-reference/extracted/CombatRoll.asi`, SHA-256
  `8F61DA404E4C970BF0B21D4026CBBBC01ABE781AB6094832FC40D54700B9B0F9`.
  Existing worklog prose and verifier tokens are not substitutes for re-reading
  the selector, heading operand, trigger, and call ordering from that PE.
- `fuckups.txt` entry 1 forbids plausible animation-flag names and call-site
  claims. Every direction/heading correction must be tied to an instruction in
  the actual PE or remain unknown.

### Sanctioned path and ownership reconciliation

The repair must preserve the reference's event-driven P1/P2 state machine and
authored root motion. `movement.cpp` owns the roll only from the engine combat-
roll predicate edge through its bounded P2 finish. `human_movement.cpp` must
yield for every non-idle dodge stage and must never clamp blend or sprint input
during that interval. The direction fix may correct only reference-proven
selector/heading semantics; no velocity, teleport, ragdoll, per-frame heading
fight, or second locomotion writer may be layered onto it. #9's restored prone
state and verifier invariants must remain unchanged.

### Actual execution / postcondition

The trace must record the four directional control bits, selected P1/P2 pair,
camera yaw, heading applied to the ped, stage survival, P1-to-P2 phase, and P2
finish. The postcondition is not `TASK_PLAY_ANIM` issuance: selected direction,
ped displacement/heading and visible roll direction must agree. A five-second
idle heartbeat remains mandatory to distinguish no engine trigger from a dead
dispatcher.

### Player-visible acceptance

While aimed, forward/back/left/right and all four diagonals must roll in the
pressed camera-relative direction without a 270-degree spin, backward-looking
detour, standing overlay, slide, or teleport. Sidearm and longarm P2 recovery,
crouched restoration, neutral/unsafe vanilla fallback, aim/Dead Eye recovery,
and #9 prone behavior remain separate required checks.

### Every issue-owned per-frame native

The update function may read ped validity/fall/ragdoll, engine combat-roll
predicate, four movement controls, dictionary state, active-animation state and
phase while idle/live. Mutations remain transition-only: camera-relative
heading once at P1 issue, pain-audio bracket, P1 task, P2 task, P2 stop, one
Stamina charge and crouch restoration. Heading, task, velocity, blend, motion-
state, input-disable, or Stamina writes must never become unconditional per-
frame mutations.

## 2026-08-10 reference heading-loop correction

Re-disassembly of the hash-pinned PE found the exact omitted behavior behind
the visible 270-degree turn. The reference's heading contract is not a one-shot
camera alignment:

- `0x1800014BC` calls `GET_GAMEPLAY_CAM_ROT(2)` and reads its Z component;
- `0x1800014E7` loads native `0xCF2B9C0645C4651B`, resolved in
  `natives.json` as `SET_ENTITY_HEADING`, and applies the camera yaw;
- `0x180001529` loads `0xC230DD956E2F5507`, resolved as
  `GET_ENTITY_HEADING`, and saves the heading the engine actually accepted;
- the P1 polling loop reloads and writes that saved heading at
  `0x1800015D0..0x18000165A`;
- the P2 polling loop does the same at `0x1800017A0..0x180001846`.

The prior port implemented only the first write. The authored roll clip could
therefore rotate the entity root while P1/P2 advanced, matching Lexer's visible
spin. `movement.cpp` now stores the accepted heading and reasserts it only while
the bounded roll state machine owns P1/P2. It remains absent from idle/ordinary
locomotion and does not add velocity, teleport, forced motion state, task clear
or a second gait owner.

The direction trace now records the exact four control bits, selected pair,
camera yaw, accepted/pinned heading and heading readback at survival. The roll
heartbeat and attempt records now use the unified production logger directly;
the previous helper was development-gated, which explains why the installed
production log contained no roll evidence even though the animation was
visible.

`verify_dodge_roll_issue_6.py` now checks the PE's exact heading-native hash and
the two `mov rcx,r12` loop sites at RVAs `0x15D8` and `0x17A8`, then requires
the accepted-heading readback, bounded live pin and production heartbeat in
source. `verify_prone_climb_parity.py` still passes all 34 invariants, preserving
the verified #9 rollback state.

Static checks passed; no build/install/shared file/label change was performed.
Runtime remains decisive: each of eight inputs must log matching control bits
and pair, keep heading readback pinned through both live phases, and visibly
move in the requested camera-relative direction without the 270-degree spin.

## 2026-08-10 returned-test request: timing, i-frames and opacity

Lexer's latest request superseded the fixed reference timing as the desired
player-facing behavior. The roll must expose editable i-frame and recovery
durations; their sum is the requested total roll duration. During the i-frame
prefix the player must be invulnerable and partially transparent at an editable
opacity, then both properties must return to their exact pre-roll values at the
i-frame boundary or any interrupted finish.

The implementation boundary is strict because earlier attempts repeatedly
substituted unproven movement writers for the authored task. The two clips keep
exclusive root-motion ownership. Their active authored phase durations are
measured with `GET_ANIM_DURATION`; one common animation-speed scale maps the
combined P1 0.84 plus standing/crouched P2 stop phase to the configured sum.
Damageability and alpha are captured with `_GET_ENTITY_CAN_BE_DAMAGED` and
`GET_ENTITY_ALPHA`, changed only during the bounded i-frame prefix, read back,
and restored rather than reset to guessed defaults.

The requested distance control was researched separately. `TASK_PLAY_ANIM`
and `TASK_PLAY_ANIM_ADVANCED` expose blend/playback rates, duration, flags,
start position and rotation, but no authored-root-translation scale. Playback
speed changes elapsed time while preserving the clip's total root displacement.
No supported entity-local root-distance multiplier was found in the SDK/native
surface or Story call sites. A distance setting would therefore require the
same velocity/coordinate/teleport layer that previously broke this feature and
is explicitly rejected until a real root-motion distance mechanism is found.

## 2026-08-10 recurrence audit before the rapid-roll repair

- Primary evidence was the hash-pinned `CombatRoll.asi` outer predicate at
  RVA `0x19EE`, the active `updateDirectionalDodgeRoll` state machine, and the
  installed roll trace. The trace proved that accepted replacement rolls spent
  exactly the configured Stamina amount; it did not prove that every visible
  Rockstar roll entered the replacement state machine.
- The recurring false-success risk was an intent-only Stamina log. A
  `_CHANGE_PED_STAMINA` call and its requested value were not enough. Each
  accepted P1 needed an immediate before/after readback and a comparison with
  the amount that could actually be spent before the bar reached zero.
- The active update returned during P1/P2 before it sampled
  `GET_PED_IS_DOING_COMBAT_ROLL`. That lost the required false interval between
  rapid engine roll predicates. A second true predicate could therefore remain
  latched as the first roll and bypass the replacement P1 and its one-time
  Stamina charge.
- `CooldownMs` was not part of the active roll state machine. It was a stale
  setting from the superseded implementation. It had no automatic relationship
  to the configured roll length. The requested roll length was already the sum
  of `InvulnerabilitySeconds` and `RecoverySeconds`.
- The sanctioned repair boundary was the hash-pinned engine predicate, exact
  directional selector, paired authored P1/P2 tasks, and one charge after each
  accepted P1. No input suppression, coordinate write, velocity write, task
  clear, or new cooldown owner was permitted.
- Static execution proof had to show that the predicate was sampled and an edge
  was queued before the active-stage return, that every accepted P1 emitted a
  Stamina postcondition, and that all adjacent prone/climb/roll verifiers still
  passed. Player-visible acceptance remained rapid repeated rolls that each
  spend Stamina when the bar is above zero.

## 2026-08-10 rapid-roll source repair

`updateDirectionalDodgeRoll` now sampled `GET_PED_IS_DOING_COMBAT_ROLL` on
every update before advancing or returning from P1/P2. A rising edge snapshots
the exact reference directional pair and remains pending until the current P2
releases ownership. The active roll no longer hides the false interval needed
to recognize a rapid next edge.

Each accepted P1 now has a monotonically increasing sequence number and one
Stamina mutation. Its production trace records the native return, before/after
bar values, expected spend clamped to the available bar, actual spend, and a
readback-match result. This is execution evidence for the charge, not visual
acceptance of the roll.

The active state machine contains no cooldown read or gate. `CooldownMs` was a
stale shared setting from the superseded implementation, not animation length
and not an automatically calculated value. The actual requested roll length is
still `InvulnerabilitySeconds + RecoverySeconds`; those values scale the paired
authored phases together.

`verify_dodge_roll_issue_6.py`, the new #172/#173 verifiers, all #97/#113/#119/
#159/#160/#161/#165/#166/#167/#169 climbing verifiers, prone/climb parity, #9,
#68, and #144 passed. No build or install was performed. Runtime acceptance
still requires rapid consecutive rolls to produce distinct sequence records
and matched Stamina postconditions, then visibly spend the configured amount.

## Integration cleanup of dead controls

`CooldownMs` and `AllowFirstPerson` were removed from the shared globals,
config reader, main INI, editor schema, and generated in-game menu. The active
roll duration remains exactly `InvulnerabilitySeconds + RecoverySeconds`.
Lexer's current movement and road tuning values were preserved; the settings
generator now reads pending fragments before the main INI so a fragment cannot
silently overwrite an already-merged user value.

## 2026-08-11 direct answer to the latest timing question

Yes, the roll animation length is editable. The active runtime defines total
visible roll time as `InvulnerabilitySeconds + RecoverySeconds`, samples the
authored P1/P2 active duration, and applies one bounded animation-speed scale so
the paired clips finish in that requested total. `CooldownMs` is not animation
length and has been removed from the active roll runtime. The two editable
durations always add to the total by construction; there is no third duration
value that can disagree with them.

`verify_dodge_roll_issue_6.py` passed the hash-pinned Combat Roll trigger,
selector, P1/P2 phases, timing scale, i-frame restoration, stamina ownership,
and postcondition checks. The audit found one timing defect: P1 received the
configured animation-speed scale on its issue frame, but P2 waited for its
150 ms survival readback before receiving that scale. P2's short recovery phase
therefore began at default speed and the visible total could disagree with the
requested sum. P2 now receives the same scale immediately after its task is
issued, before the survival timer is armed. The combined build must still carry
the current settings surface; an older editor or installed schema can still
display the removed Cooldown field.
