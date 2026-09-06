# GitHub #1 - Campfire issues

## Latest runtime correction

Lexer tested the installed first attempt twice and reported that neither
requested behavior worked. The implementation was therefore treated as failed,
not as awaiting another identical test.

The two concrete mistakes were:

- `INVENTORY_DISABLE_ITEM` only disabled the kit. It did not meet the request
  that the camp item be absent from the radial.
- `player_camp.c` uses two teardown inputs. The ambient long hold uses
  `INPUT_CONTEXT_B`, but the camp-menu medium hold is explicitly remapped by
  `func_758` to `INPUT_PCAMP_TEARDWN`. The first implementation watched only
  `INPUT_CONTEXT_B`. It also disabled that action after the standardized prompt
  had already started filling, without resetting the prompt's input value.

## Replacement implementation

Outside missions, the policy now removes both `KIT_CAMP` and
`KIT_CAMP_SIMPLE` from the live inventory rather than leaving disabled radial
entries. The removed counts are persisted in `camp-kit-policy.state`, so a game
reload does not lose the player's entitlement. Mission entry enables both
records and restores the persisted counts; while the mission is active the
Story scripts own any grants, swaps, use, or consumption. Mission exit captures
the resulting variants again. Removal and restoration are verified from live
inventory counts and failures remain scheduled for retry.

For authored camps, `INPUT_PCAMP_TEARDWN` is disabled every frame inside the
owned `player_camp` footprint. The shared ambient `INPUT_CONTEXT_B` action keeps
its first 150 ms so short Leave/back interactions remain possible; a sustained
press is then disabled in all three relevant groups and forced to a zero value
with `SET_CONTROL_VALUE_NEXT_FRAME`, resetting the standardized teardown hold.
Issue #116's separate F3 hold-removal path remains untouched.

## Evidence and test boundary

- Decompiled `player_camp.c` creates the ambient `CAMP_TEARDOWN` prompt as a
  `LONG_TIMED_EVENT` on `INPUT_CONTEXT_B`.
- Its camp-menu prompt starts as medium-hold Leave and is explicitly remapped to
  `INPUT_PCAMP_TEARDWN` before its text changes to `CAMP_TEARDOWN`.
- `GameplayTweaks.campfire-policy.log` records session bank state and the
  before/after inventory count for every bank/restore attempt, including
  explicit `bank-failed` and `restore-failed` outcomes.
- `python tools/reverse-engineering/verify_campfire_policy_issue_1.py` checks
  registration, physical removal and persistent mission restoration, both
  teardown controls, hold reset, runtime logging, and preservation of #116.

The replacement was only statically verified in this worktree. It was not built
or installed here. After integration, the player-visible acceptance checks are:

1. In free roam, neither camp-kit variant appears in the item radial.
2. At a saved authored campsite, neither the ambient nor camp-menu teardown hold
   can remove the physical camp; short Leave/back still works.
3. F3 hold still intentionally removes the authored campsite and its saved row.
4. A mission that supplies or requires camping can expose/use its camp kit; on
   return to free roam the kit is absent again.

## Current actionable pass

The prior control block could never hide the always-visible world prompt:
`player_camp.c:1342` registers a distinct `CAMP_TEARDOWN` prompt with prompt
type 1. While an authored camp is active, GameplayTweaks now calls Rockstar's
`_UIPROMPT_DISABLE_PROMPT_TYPE_THIS_FRAME(1)` before presentation. Other camp
interactions use type 0 and remain visible. The menu's dedicated teardown action
is still blocked, and the shared B hold is cut off at 80 ms—before its separate
Leave prompt can relabel at 100 ms—while a normal tap remains available. The
updated issue verifier passes.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 prompt-registry correction

The installed prompt-type suppression did not hide the world teardown prompt.
The replacement scans Rockstar's 48-entry live prompt registry and hides only
an active `INPUT_CONTEXT_B` prompt that actually has hold mode. This leaves the
ordinary short Leave/back prompt, which shares the action but is not hold-mode,
visible and usable. The dedicated `INPUT_PCAMP_TEARDWN` action remains blocked.

The acceptance check is the requested player behavior: the authored camp has
no usable or visible teardown hold, while a normal short Leave/back tap still
works. F3 is a compiled-out developer authoring control and is not part of #1's
player acceptance path.

## 2026-08-10 live prompt-registry field correction

The next installed test still showed the complete teardown prompt and allowed
its cutscene to run. The registry scan had not actually inspected an allocated
prompt: `player_camp.c` `func_395` writes the allocation flags to
`Global_1945938[index].f_1`, the prompt handle to `f_3`, and the control action
to `f_4`. The module incorrectly tested the base `f_0` field for bit 2. For the
ambient teardown constructor, `f_0` is zero, so every matching prompt was
rejected before its handle or action was examined.

The scan now tests `record + 1`, then narrows the result to a valid hold-mode
prompt whose `f_4` action is `INPUT_CONTEXT_B`. It hides and disables that
exact prompt every protected frame. The physical camp-kit banking remains
unchanged because the live test already confirmed the campsite item is absent
from the radial. This pass was statically verified only; absence of the prompt
and refusal of the teardown cutscene remain in-game acceptance checks.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- The actionable complaint is player-visible prompt and notification behavior; a successful registry scan alone is not acceptance.
- The repaired prompt path reads and suppresses the exact live hold-mode teardown prompt and blocks its actual remapped action, while preserving short-B input. Runtime acceptance still requires the requested vanilla-style notification and absence of every reported campfire prompt.

## 2026-08-10 full latest-acceptance repair

The latest screenshot was inspected before this pass. It proves both reported UI
failures in one frame: `Campsite activated. You can now respawn here.` is drawn
as the small custom centre-left debug text, and the complete right-side
`TEAR DOWN CAMP  F` prompt remains visible alongside the valid camp actions.

The installed `GameplayTweaks.log` supplies two concrete causes that the prior
candidate ignored:

- proximity records repeatedly reported a saved site with `refs=1` while
  `trackedThread=0`; the prompt guard nevertheless required the ASI's tracked
  `g_materializedCamp` and active `g_campThread`. A real authored camp could
  therefore be running and visible while the guard returned before inspecting
  a prompt;
- the installed heartbeat reported `runtimeDev=0`. The F3 key was guarded by
  `developmentModeActive()`, so the exact 800 ms #116 removal body was
  unreachable in the installed release build. The earlier statement that F3
  was not player acceptance is superseded by Lexer's explicit latest test and
  by closed issue #116's acceptance contract.

The notification failure was direct in source: every campsite result only set
`g_campMessage`, and `updateCampsites` rendered it with `drawReconText` at
screen coordinates. That was a debug overlay, not a vanilla notification.

### Re-audited acceptance points

1. Outside missions, both camp-kit variants remain physically banked and absent
   from the radial. The latest tests already confirmed radial absence; mission
   restoration and return-to-free-roam rebanking still require runtime proof.
2. At any saved authored-site footprint, the vanilla teardown prompt must never
   render and neither the ambient nor menu teardown action may execute.
3. Holding F3 for 800 ms anywhere within that same 30 m footprint must remove
   the saved row and request cleanup of the physical camp. Tapping inside the
   footprint must still refuse duplicate placement, preserving #116.
4. Campsite placement, activation, removal, invalid-area and not-at-camp status
   messages must use the vanilla large top-left black-background tooltip, never
   `drawReconText`.

### Primary evidence and sanctioned path

- `player_camp.c:1342` constructs the ambient teardown through
  `func_158("CAMP_TEARDOWN", INPUT_CONTEXT_B, 0, 1, 0, 5, ...)`.
- `player_camp.c` `func_395` records prompt context at `f_0`, allocation flags
  at `f_1`, constructor parameter 1 at `f_2`, the prompt handle at `f_3`, the
  action at `f_4`, and owner thread at `f_16`. `_GET_HASH_OF_THREAD` is resolved
  as `0x724CB89D35B283D0` in the SDK and lets the repair require a
  `player_camp` owner rather than guessing from an input alone.
- `player_camp.c` `func_76` posts ordinary help through a four-field settings
  struct, two-field content struct and `UIFEED::_SHOW_TOOLTIP`; the SDK resolves
  that native as `0x049D5C615BD38BAD`. Campsite messages now copy that exact
  Story wrapper instead of inventing presentation.
- Saved-site ownership is the existing #116 30 m footprint. It no longer
  depends on the asynchronous launcher remembering the currently running Story
  thread. No campsite row, radius or launch policy was changed.

### Execution proof and every per-frame native

On first matching registry acquisition, the module logs slot, handle and owning
thread. It writes visible=false and enabled=false, then reads
`_UIPROMPT_IS_ENABLED`; an enabled readback is an explicit error. The cached
handle is revalidated at 4 Hz rather than rescanning and rewriting 48 prompts
every frame. A newly created prompt is found through read-only global fields;
only a record matching `f_0=0`, `f_2=1`, `INPUT_CONTEXT_B`, and a
`player_camp` owner reaches `_GET_HASH_OF_THREAD`, prompt-valid and hold-mode
natives. This acquisition scan runs each frame only until the exact prompt
exists so it can be hidden before presentation.

The two per-frame mutation paths are the controls that Story reads in the same
frame: `INPUT_PCAMP_TEARDWN` is disabled for control groups 0-2, and a sustained
`INPUT_CONTEXT_B` is disabled/zeroed after 80 ms. Those cannot be moved to a
slower poll without allowing teardown input between polls. Short B remains
untouched during its first 80 ms. The broader saved-footprint check uses the
existing per-frame player-coordinate read already required by campsite
streaming; it adds no invented engine state.

Each call to the vanilla tooltip logs the returned feed handle and message.
Holding F3 logs `removal-hold`, including the chosen site and distance. These
prove execution, not appearance or cleanup.

### Static evidence and runtime boundary

The following issue-local checks passed:

```
python tools/reverse-engineering/verify_campfire_policy_issue_1.py
python tools/reverse-engineering/verify_campsites_issue_116.py
python -m py_compile tools/reverse-engineering/verify_campfire_policy_issue_1.py
```

Integration must compile the changed `campfire_policy.cpp` plus the campsite
section of `world_economy.cpp`; no dispatcher registration is required. Runtime
acceptance still requires a fresh game test: verify the large vanilla top-left
notification, complete absence of `TEAR DOWN CAMP`, a successful 800 ms F3
removal with physical cleanup and saved-row deletion, short-B behavior, no
duplicate on F3 tap, free-roam radial absence, and mission kit restoration.

## 2026-08-10 returned test: Leave Fire was blocked

Lexer reported that pressing F on `Leave Fire` immediately removed the prompt
and made it impossible to leave camp. The cause was the module's deliberately
broad fallback: after 80 ms it disabled and zeroed `INPUT_CONTEXT_B` for groups
0-2. `player_camp.c` uses that same input for its medium-hold `LEAVE` prompt, so
the fallback necessarily broke the valid action while trying to pre-empt the
later teardown relabel.

The shared input fallback was removed completely. Protection now has only two
narrow targets: the exact ambient `CAMP_TEARDOWN` prompt handle is hidden and
disabled, and the camp menu's separately remapped `INPUT_PCAMP_TEARDWN` action
is disabled. `INPUT_CONTEXT_B` is never disabled or zeroed by this module.
Runtime acceptance remains required for both sides of the correction: holding F
must leave the fire normally, while the authored campsite teardown prompt and
teardown action remain unavailable.

## 2026-08-10 integration regression: free-roam inventory churn

Before changing source, the #114 returned-shop trace was reconciled with #1's
camp-kit owner. The installed free-roam session had one banked full camp kit and
no live kit, but `updateCampfirePolicy` still called `INVENTORY_ENABLE_ITEM` on
both kit hashes every 500 ms before checking their counts. Those writes were not
part of #1's requested steady state; the kit was already absent. They also
mutated the same shared inventory layer while Story shop scripts tried to own
their transactions.

The repair keeps free-roam enforcement read-only unless a kit count is actually
positive. Mission-entry still enables and restores both banked records once;
mission-exit and later free-roam grants are banked on the existing 500 ms poll.
This preserves the radial/mission contract without a permanent inventory
writer. Static checks must reject any unconditional free-roam enable call.

The exact prompt/ownership correction was installed with the complete adjacent campfire verifier set in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`. Prompt absence, Leave Fire, F3 removal and crash-free runtime remain `test me`.

## 2026-08-10 returned F3 crash recurrence audit before source repair

- Lexer reported that holding F3 still immediately ended the game. GitHub #1 moved from `test me` back to `actionable`; closed #116 was not reopened.
- The retained exception trace is decisive about the failing call boundary: access violation at `RDR2.exe+0x25F799A`, then stack overflow, both while `g_crashTraceStage` was `campMessage.showTooltip`. F3 reaches that stage only after the saved-row/blip cleanup, when it posts the removal status.
- The preceding raw-string attempt and the current `_CREATE_VAR_STRING` attempt have both crashed inside the same undocumented `_SHOW_TOOLTIP` ABI. Static resemblance to decompiled `player_camp.c` did not establish a ScriptHook-safe call contract. It must not be wrapped, padded, deferred, or tried again in another form.
- Repair boundary: remove `_SHOW_TOOLTIP` and `_CREATE_VAR_STRING` from the campsite message path completely. Preserve the exact F3 hold, saved-row deletion, blip removal, physical `player_camp` cleanup request, persistence write and structured log. A missing cosmetic notification is safer than another fatal native call and remains explicitly unresolved rather than being described as accepted.

### Installed crash-path removal

- `_SHOW_TOOLTIP`, `_CREATE_VAR_STRING` and `campfireVanillaTooltip` are absent from the campsite path. `campMessage` is now a structured unified-log record only; it performs no UI native call.
- The #1, #116, #164 and #149 camp verifiers passed together, including explicit rejection of the fatal tooltip path and preservation of the F3 removal transaction.
- Development ASI `A683281C943827B54EAD6D1107FBD5273155A2A01CA345F1C76528BA0A009B4B` was installed with RDR2 closed; source and game-root hashes matched. #1 moved to `test me` only after installation.
- Runtime acceptance is narrowly F3 removal without `ERROR:FFFFFFFF`, with the saved marker/row and physical camp removed. A cosmetic player-facing campsite status notification remains unresolved and is not being claimed.

## 2026-08-11 coupled #1/#164 prompt audit

Lexer's confirmed long-F3 campsite removal was preserved without any source
change to its 800 ms hold, saved-row deletion, blip removal, physical cleanup,
CSV save or log-only status path. The fatal `_SHOW_TOOLTIP` and
`_CREATE_VAR_STRING` calls remained absent.

The free-roam radial policy was also left unchanged. It still banks only a camp
kit that is actually present, reads back the live count, and restores a
genuinely banked item on mission entry. No steady-state free-roam inventory
enable writer was returned.

The coupled teardown repair corrected only stale exact-prompt ownership. The
cache now proves that its saved slot still contains the same `player_camp`
owner thread, priority, transport, handle and Context-B action before it hides
or disables the prompt. The standing priority-0/transport-1 handle and seated
priority-2/transport-0 handle remain separate. The priority-1 short `Leave`
handle is excluded, and Context-B is never suppressed. A bounded heartbeat and
enabled/active readbacks were added so the next installed test can show whether
Rockstar created each exact prompt and whether suppression persisted.

Both issue-local verifiers passed. This did not compile or install an ASI and
did not prove any screen result. Integration must include the changed policy,
run the adjacent camp/inventory checks, install once, then keep #1 and #164
actionable until the radial mission transition and all three teardown surfaces
are confirmed in game. The already confirmed long-F3 removal is not a new test
request.
