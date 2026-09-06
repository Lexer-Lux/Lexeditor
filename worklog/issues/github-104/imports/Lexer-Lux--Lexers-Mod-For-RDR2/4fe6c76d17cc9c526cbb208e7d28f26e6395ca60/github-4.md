# GitHub #4 - Binocular Quick Access Presentation

## Requirement

Holding the Cover button for quick binocular access must use Arthur's vanilla
satchel retrieve and return presentation. The binocular prop must not appear in
or disappear from his hands instantly. A short Cover press remains native.

## Cause

The quick-access path selected the binocular kit with
`SET_CURRENT_PED_WEAPON(..., false, ...)`, but never started the corresponding
weapon-swap task. Non-immediate selection is only half of Rockstar's authored
transition. The active loop then repeated the selection every frame until the
kit became current, which could continually restart the transition.

The return path was reversed: it released forced aim, waited for the configured
stow duration, and only then selected the previous weapon. There was therefore
no put-away task during the supposed animation window; at its end the prop
could only disappear through the late weapon selection.

## Shipped-script evidence

Rockstar scripts consistently pair non-immediate `SET_CURRENT_PED_WEAPON` with
`TASK_SWAP_WEAPON` (native `0xA21C51255B205245`, script-task hash `716706914`).
Examples include `act_caunc_rustling.c` `func_638`, which selects a weapon with
the force flag false and starts `TASK_SWAP_WEAPON(..., 1, 0, 0, 0)`, and the
ordinary player put-away sequence documented for #82. Decompiled task guards
treat status 0 or 1 as queued/running.

## Implementation

- The binocular retrieve now selects the owned kit non-immediately and starts
  the authored swap task exactly once.
- The active loop no longer reissues the equip request each frame.
- Forced aim waits for both the configured minimum draw time and completion of
  the queued/running swap task, so the scope cannot cut off the satchel motion.
- Release now lowers forced aim, immediately selects the saved previous weapon
  non-forced, and starts the native return swap task. The stow window no longer
  issues a second late weapon selection.
- `InstantEquip=1` remains an explicit compatibility/debug escape hatch and
  intentionally retains immediate behavior; the shipped default is 0.

No dispatcher, build/install script, generated knowledge index, GitHub state,
or unrelated issue worklog was changed.

## Static verification

- Confirmed both transition directions use non-forced selection when
  `InstantEquip=0` and are paired with `TASK_SWAP_WEAPON`.
- Confirmed the draw task is issued only by the one-time entry request, not the
  active per-frame branch.
- Confirmed forced aim is gated while task status is 0/1.
- Confirmed the release branch requests the return before starting its stow
  window and the stow completion branch performs no second selection.
- `git diff --check -- GameplayTweaks/modules/combat_inventory.cpp
  worklog/issues/github-4.md` passed.
- Per feature-agent policy, no compile, link, install, game launch, commit, push,
  or GitHub mutation was performed.

## In-game acceptance

1. On foot with binoculars owned and `InstantEquip=0`, briefly tap Cover: Arthur
   should only perform normal Cover behavior.
2. Hold Cover past `HoldMs`: Arthur must visibly reach to the satchel, retrieve
   the binoculars, raise them, and only then enter the scope.
3. Release after the scope is up: Arthur must lower the binoculars and visibly
   return them to the satchel; they must not blink out of his hands.
4. Repeat from empty hands and while a normal weapon was previously selected;
   the prior selection must be restored without interrupting either binocular
   transition.
5. Confirm the log contains one `satchel retrieve task requested` and one
   `native satchel stow task requested` per complete use, with no equip timeout.

## Remaining boundary

Static evidence proves the missing task ownership and reversed stow timing were
repaired, but only the requested in-game pass can confirm that the player
locomotion graph chooses the exact expected satchel clips in every stance.

## 2026-08-10 returned-test correction — one-frame prompt flash

The combined installed build
`E3CADC51EEAD96B3A45958ECBE41E99A29F376944B9C28E92ABB88717E7235AA`
executed the binocular path: the installed `GameplayTweaks.log` recorded raw
cover edges, one retrieve request, active binocular pulses, release and one
stow request. The returned test nevertheless still showed the Backspace
put-away prompt for a fraction of a second during retrieval.

The exact cause was ordering, not a wrong prompt hash. Decompiled
`binoculars.c` state 2 calls `func_20("BINO_PUT_AWAY",
INPUT_CAMERA_PUT_AWAY, ...)`; `func_20` registers the prompt and its constructor
immediately calls `func_54(..., true)` and `func_55(..., true)`. The former #4
repair scanned the global registry for that new handle. When Rockstar's script
registered the handle later in the same frame, no handle existed during our
scan and the constructor displayed it for one frame before the following scan
hid it.

`combat_inventory.cpp` now calls the authoritative per-frame native
`HUD::_UIPROMPT_DISABLE_PROMPTS_THIS_FRAME()` before equipping the binocular
kit and on later ownership frames only until the exact prompt handle becomes
available. This removes the same-frame registration race regardless of
script-thread order without suppressing unrelated/zoom prompts after the
put-away handle is known. The existing narrow `INPUT_CAMERA_PUT_AWAY` registry
scan remains and now logs the discovered handle plus valid/active readbacks
after hiding it; no Rockstar-owned prompt is deleted.

Scoped static verification passed with
`python tools/reverse-engineering/verify_binocular_quick_access_issue_4.py`.
No build, install, manifest or label change was performed in this issue-local
repair. Runtime acceptance still requires confirming there is no flash from
the first retrieve frame through stow while ordinary prompts return immediately
after quick binocular ownership ends.

The live test showed the swap task froze locomotion and introduced a second
fixed wait after Arthur had already retrieved the binoculars. Retrieve/stow now
use Rockstar's locomotion-compatible swap option, scope entry waits only for
the real task completion, and the native Backspace cancel action is suppressed
while the hold-to-use path owns binoculars.

## Returned-test correction: active-view movement and prompt

The next live test confirmed that the revised swap options fixed locomotion
during retrieval and return, but Arthur still could not move while the
binocular view was active and the bottom-right put-away prompt remained.

The prompt suppression had targeted `INPUT_FRONTEND_CANCEL`. Decompiled
`binoculars.c` proves the displayed `BINO_PUT_AWAY` prompt is registered against
the distinct `INPUT_CAMERA_PUT_AWAY` action. Quick access now disables that
exact action and scans the 48-entry shared prompt registry only for a valid
entry whose stored action is `INPUT_CAMERA_PUT_AWAY`; that matching prompt is
made invisible and disabled each frame without deleting Rockstar-owned prompt
state or affecting any unrelated prompt.

The active looking-glass control context consumes ordinary locomotion even
though the physical movement values remain readable. While quick access is
active, the runtime now restores player control if that context disabled it,
re-enables only `INPUT_MOVE_LR` and `INPUT_MOVE_UD`, and replays their current
keyboard/gamepad values into gameplay groups 0 and 2. Look, aim, zoom,
retrieve/stow, and all unrelated actions remain native. Improved-binocular
selection from #59 is unchanged.

Static verification passed:

- `python tools/reverse-engineering/verify_binocular_quick_access_issue_4.py`
- `git diff --check -- GameplayTweaks/modules/combat_inventory.cpp
  tools/reverse-engineering/verify_binocular_quick_access_issue_4.py
  worklog/issues/github-4.md`

This is not runtime acceptance. After integration, build, and installation,
test walking forward/backward and strafing with both keyboard and controller
while the scope is fully up. Confirm the put-away prompt is absent, zoom/look
still work, release still performs the satchel return, and the improved item
still uses its distinct optics.

## 2026-08-09 Q hold stopped after recon use

The session log proved physical Q quick access had worked once, then Lexer
reported that later holds did nothing. The start gate combined actual free aim
with `IS_PLAYER_TARGETTING_ANYTHING`; the latter is broader than physical aim
and can remain true after a recon target is released, leaving every later Q/RB
hold ineligible even though no gun is visibly being aimed.

The start gate now checks the real Aim action in gameplay groups 0/2, raw RMB,
and the active aim camera only. It no longer consults the sticky target state.
Physical Q/RB down/up transitions are logged once per edge so a failed hold can
no longer be invisible between three-second heartbeats.

Development ASI
`F1852A53EA48C933C9E12420E3CC8589C34E3D8FA4FCA0D31EE63B28DC89BF28`
was built and installed while RDR2 was closed. Source, game-root ASI and release
manifest hashes matched. Runtime acceptance requires repeated hold-Q binocular
entry before and after tagging/aiming, plus ordinary tap-Q Cover behavior.

## 2026-08-10 extended-session input-gate correction

The unified log recorded physical Cover down/up transitions after extended
play but no hold/entry line. `aimingAGun()` had already stopped consulting the
sticky target predicate, but it still treated `CAM::IS_AIM_CAM_ACTIVE()` as
physical input. Rockstar can leave that camera state latched after the actual
Aim input is released, permanently blocking a later binocular hold.

The entry gate now reads only the real Aim controls and RMB. Camera state no
longer vetoes a new hold. The active binocular path remains self-owned once it
has begun, and weapon-wheel suppression is unchanged.

## 2026-08-10 one-frame put-away prompt correction

The latest live test confirmed quick access was otherwise close, but the
Backspace put-away prompt flashed during the draw. The narrow prompt scan was
using the correct handle (`f_3`) and action (`f_4`) offsets but tested the wrong
allocation field first. `binoculars.c`'s shared constructor writes the active
bit to `Global_1945938[index].f_1`; the module read `f_0`, so the scan skipped
the newly registered `INPUT_CAMERA_PUT_AWAY` prompt instead of hiding it.

The scan now reads `record + 1` before matching `record + 4` and suppressing
the valid `record + 3` handle. Native satchel draw/stow, locomotion bridging,
and Story binocular selection are unchanged. This pass was statically verified
only; the acceptance check is that Backspace never appears, including the first
draw frame.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## Recurrence audit before the pre-optics tag repair

This audit was written before changing the returned source, after reading
`fuckups.txt`. The latest player-visible failure is precise: a ped near screen
centre begins receiving the recon fade/tag presentation during the satchel
draw, before the binoculars reach Arthur's face.

### Primary evidence/reference

- `combat_inventory.cpp` currently sets `forcedAim=true` immediately after the
  swap task becomes idle, then publishes `g_binocularsActive = isBino &&
  forcedAim` in that same frame. `forcedAim` is an issued setter state, not a
  camera/optics readback.
- `recon.cpp` treats `g_binocularsActive` as sufficient to run the reticle probe,
  acquisition and overlay path. Thus the installed symptom follows directly
  from the published state even if the optics camera has not become active.
- Decompiled `binoculars.c` is the required sanctioned-state reference. A true
  camera/view or script-state readback must be opened and resolved before this
  attempt substitutes a new predicate.
- Installed/runtime execution proof must distinguish: swap complete, forced-aim
  request issued, true optics ready, recon acquisition enabled, and first
  marker rendered. A setter call or equipped binocular hash proves none of the
  later states.

### Sanctioned path and player-visible acceptance

Rockstar's satchel draw and binocular camera remain owners of presentation.
Quick access may request the authored swap and forced aim, but recon may become
active only after a true binocular-ready readback. Once ready, the existing
aim-to-tag behavior must remain unchanged. Acceptance is that no target icon,
fade, study meter, or acquisition starts anywhere in the draw; it begins only
after the binoculars are visibly against Arthur's face and the optics view is
active, then continues normally while aiming through them.

### Every relevant per-frame native before this repair

During draw/active/stow, prompt ownership scans up to 48 registry records and,
for a matching handle, calls `_UIPROMPT_IS_VALID`, `_UIPROMPT_IS_ACTIVE`,
`_UIPROMPT_SET_VISIBLE`, `_UIPROMPT_SET_ENABLED`, then validity/active readbacks.
Before a handle is found it calls the broad
`_UIPROMPT_DISABLE_PROMPTS_THIS_FRAME`; every owned frame also calls
`DISABLE_CONTROL_ACTION` for `INPUT_CAMERA_PUT_AWAY` in groups 0, 1 and 2.
The broad guard is not sanctioned as an exact-prompt operation and must not be
allowed to suppress unrelated prompts after an exact handle can be observed.

The active quick-access path also performs per-frame weapon/binocular state,
swap-task and camera queries; the transition-rate observer can call
`IS_ENTITY_PLAYING_ANIM` across every candidate dictionary/clip and applies anim
speed only after a positive readback. Locomotion bridging reads player-control
and two axes every frame, conditionally restores control, then enables/replays
only those axes. The recon path independently queries held weapon/binocular
type, aim controls/camera, performs its reticle probe/acquisition and renders
owned overlays. The repair must gate that recon work at its entrance with the
resolved true-ready state, not merely hide a marker after acquisition began.

## Returned-test repair: Rockstar optics-ready gate

`binoculars.c:486-496` provides the sanctioned readback: its `func_21` advances
the binocular thread from on-foot setup to `BINOCULARSINUSE` only when
`CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE()` is true. `func_27` at `:596-603` exits
that state when the same predicate becomes false.

Quick access now samples that camera predicate once per owned frame. A forced-
aim request made on the current frame cannot publish readiness; a later frame
must positively read the first-person aim camera. `g_binocularsActive` is now
`isBino && forcedAim && opticsReady`, and recon already excludes a held
binocular weapon from its ordinary gun-aim fallback. Consequently reticle
probing, dwell acquisition, fade presentation and Study cannot begin during the
satchel draw, while ordinary aim-to-tag remains unchanged.

The broad prompt guard was also narrowed to the only interval it can justify:
the pre-registration constructor race. A dedicated state bit now changes only
after a positive scan of Rockstar's exact `INPUT_CAMERA_PUT_AWAY` prompt handle;
from that readback onward, including stow, only the exact handle/action path is
used. Draw duration and camera state are no longer treated as evidence that the
prompt has registered. This retains the no-flash repair without blanking
unrelated prompts throughout the entire binocular session.

Static verification passed with
`python tools/reverse-engineering/verify_binocular_quick_access_issue_4.py`.
Runtime acceptance requires a centred nearby ped during the complete draw: no
icon/fade/Study may appear until the optics are visibly at Arthur's face, after
which normal aim-to-tag must work. No build, install, shared file, manifest, or
GitHub state was changed.

## 2026-08-10 recurrence audit before the latest Q-input repair

- **Primary evidence/reference:** the latest live report is “holding Q just
  does nothing.” The installed unified log starts the binocular subsystem and
  emits idle heartbeats, but the available current session contains no physical
  Cover edge, hold threshold, equip request, swap ownership, optics-ready, or
  stow line. The authoritative input source is the bindable `INPUT_COVER`
  action and its enabled/disabled control readback; the authored draw/stow path
  remains Rockstar's binocular script and native weapon-swap task.
- **Sanctioned path:** own the bindable Cover action from the first physical
  down edge, defer native Cover until release, replay only a true short tap, and
  consume a qualifying hold exactly once for the native binocular draw. Do not
  infer Q from a configurable unrelated virtual key, a sticky camera state, or
  an issued setter. Quick access must not fight Cover after it has handed the
  short tap back.
- **Execution proof:** bounded logs must distinguish raw enabled/disabled Cover
  readbacks by control group, physical edge, short-tap replay, hold threshold,
  resolved owned binocular kit, swap-task start/completion, forced-aim request,
  first-person optics-ready readback, active publication, release, and stow.
  An idle heartbeat or `SET_CURRENT_PED_WEAPON` call is not success.
- **Player-visible acceptance:** tap Q still enters native Cover; holding Q
  consistently retrieves the owned binoculars from the satchel without taking
  cover, permits movement while raised, shows no Backspace flash, starts recon
  only after the optics are at Arthur's face, and release performs the authored
  satchel return. Repeat after aiming/tagging and after several minutes.
- **Every per-frame native:** while the physical hold/owned state is active,
  input suppression is allowed only for the exact conflicting actions; prompt
  mutation must switch to the exact registered put-away handle as soon as it is
  observed. Swap/camera/weapon state may be polled only during the bounded
  transition/active state. No unconditional task clear, weapon setter, broad
  prompt suppression, or global input fight may be added.

## Returned-test repair: bindable Cover restored as the hold source

The current source contradicted its own sanctioned-path comment. Although
`coverBindingDown()` read the remappable `INPUT_COVER` action, the active update
loop ignored it and used only `GetAsyncKeyState('Q')`/raw XInput RB. The latest
installed session stayed alive and emitted idle heartbeats, but contained no
input edge or hold line; this distinguished a dead raw-input path from an equip
or camera failure.

The active detector now uses bindable Cover first and retains raw Q/RB only as
a fallback. The existing first-down suppression and release-only short-tap
replay remain unchanged, so a tap still reaches Rockstar Cover while a hold is
owned by quick access. Every physical edge now records enabled and disabled
readbacks separately for PAD groups 0 and 2 plus the raw fallback; the idle
heartbeat records the aggregate binding/fallback decision. The true optics gate
remains `isBino && forcedAim && CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE()`, so this
input repair does not reintroduce pre-optics recon acquisition.

Static verification was assigned to
`tools/reverse-engineering/verify_binocular_quick_access_issue_4.py`. Runtime
acceptance still requires both branches: tap Q must enter native Cover, while a
hold must produce the per-group down edge, threshold/equip/swap/optics logs and
the visible authored binocular draw without Cover firing. No build, install or
workflow state change was made in this pass.

## 2026-08-11 #176 prompt-ownership correction

The installed log disproved the claimed bounded behavior of the broad prompt
fallback. Across many completed quick-binocular sessions it recorded zero
positive `put-away prompt suppressed` handle observations. The
`putAwayPromptObserved` latch therefore never changed, and
`HUD::_UIPROMPT_DISABLE_PROMPTS_THIS_FRAME()` ran for the complete active view.
That removed unrelated Rockstar prompts, including the animal Study/Info path.

The blanket call and its unproved latch are removed. #4 retains only two narrow
owners: disable the exact `INPUT_CAMERA_PUT_AWAY` action, and hide/disable the
exact valid shared-registry handle if it is observed. A missing handle no longer
permits any prompt-wide mutation. #176 separately restores contextual animal
actions after the optics-ready gate. Runtime must confirm both sides together:
no persistent Backspace put-away prompt, and ordinary animal Study/Info prompts
remain available through quick binoculars.
