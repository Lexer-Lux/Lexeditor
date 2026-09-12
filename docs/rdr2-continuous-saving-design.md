# Continuous saving: proposed implementation

Issue: [#121](https://github.com/Lexer-Lux/Lexeditor/issues/121).

This design is ready for review. It is not installed. No real save is changed.
The intended result is one continuing Story playthrough. Purchases, losses,
crime, death and arrest must survive a normal restart. Normal load controls must
not offer earlier states as an undo button. Development builds retain explicit
recovery controls.

## Use the game's save owner

Use Rockstar's existing Story save process. Do not periodically call the save
native, copy live globals into a file, or write an engine save from the ASI.

The local 1491.50 `long_update.ysc.c` provides the relevant starting points:

- `func_110` owns the request loop, including the ordinary time/distance trigger.
- `func_501` checks availability, loading, player state and save-operation state.
- `func_508` waits for pending operations, checks that the current character and
  stored character agree, and starts the snapshot step.
- `func_1314` prepares the state through `func_1313`, then calls
  `SAVEGAME_SAVE_SP(-189896212)` and changes request flags.
- `func_506` queues operation zero and copies nine separate global structures.
  The first alone has 12,066 cells. Saving only `Global_40` is incomplete.

These functions establish that a save request and a finished disk save are
different events. They do not prove a supported ASI request or completion hook.
`save_menu_ui_event_handler` sets `Global_20` for a `SAVE_COMPLETE` UI event;
that event alone does not identify our request or prove durable disk contents.
Do not use it as an acknowledgement without correlating the full operation.

## Proposed state machine

1. **Observe.** Bind one explicitly selected Story profile and playthrough.
   Load its last verified generation and pending consequence record. Reject a
   changed profile, unknown game build, mission replay or Online session.
2. **Dirty.** Record a confirmed consequence with a monotonic sequence number.
   Merge repeated events into a bounded pending set. A quiet interval must not
   clear that set. Time passing alone is not a confirmed consequence.
3. **Wait for a safe save.** Let the game finish inventory transactions, death,
   arrest, loading, cutscenes and checkpoint work. Request the ordinary save
   process when its real eligibility checks pass. Do not clear blockers or
   force a character snapshot during a transition.
4. **In flight.** Capture the highest sequence covered by this request. Permit
   only one owned request at a time. New consequences stay dirty for the next
   request. A timeout is a failed or unknown save, never a successful one.
5. **Verify.** Require a correlated successful engine operation, stable output
   and a valid generation manifest. A changed timestamp or a cleared busy flag
   alone is insufficient. A failed request retains the previous good save and
   all unacknowledged consequences.
6. **Commit.** Atomically publish the generation manifest last. Acknowledge only
   the sequence captured in step 4. Recheck dirty state and request another save
   if a later consequence exists.

An engine observer and filesystem verifier need a bounded, explicit handshake.
The filesystem worker must never call natives. The game thread must never wait
on a disk copy or hold the game in a loop while a file is locked.

## Which consequences persist

| Event | Commit boundary | Failure handling |
| --- | --- | --- |
| Buy, sell, craft or consume | Confirmed transaction result and inventory readback | Keep pending if the result is partial or unknown; do not infer a sale from a count change alone. |
| Crime, bounty, honor or mission reward | The game's confirmed durable state change | Merge changes through the same sequence owner; do not maintain a competing bounty or reward balance. |
| Death | Completed respawn and the game's applied penalties | Record death pending before transition when observable; never save the dead ped as a normal world snapshot. |
| Arrest | Completed release and confiscation/payment results | Keep pending through fades and transport. |
| Mission checkpoint/retry | Rockstar's checkpoint owner | Keep checkpoint semantics separate from ordinary load; do not replay arbitrary world deltas into a mission snapshot. |
| User exit | Safe save and correlated acknowledgement | If saving fails, show a specific error and retain pending state. Never report “saved.” |
| Crash or forced termination | Last committed save plus pending record | Validate both on restart; never silently call an older state fully current. |

The last two rows expose a required technical boundary: ordinary autosaving
cannot guarantee that a consequence survives a crash during a save-blocked
mission. Strict crash persistence needs a proven, idempotent replay rule for
each supported consequence, or a game transaction hook that commits it before
the action completes. A generic “reapply inventory difference” mechanism would
duplicate scripted rewards and is rejected. The full feature remains incomplete
until this boundary is solved; a periodic autosave is not a substitute.

## Normal loading and recovery

The normal load path should select only the latest committed generation for the
selected playthrough. Cover the front end, pause menu, death/retry screen and
restart path. Hiding a pause-menu button alone does not remove the other paths.
New Game and mission replay require explicit, separate playthrough identities.
Do not delete the user's older saves or modify unrelated profiles.

Development recovery must be compiled behind the existing development-build
gate. It presents generation, timestamp, reason and validation status before an
explicit restore. Restoring creates a new recovery generation and records why
continuity was broken. A release build must not expose that control through an
INI toggle. External file replacement cannot be made tamper-proof by this local
mod; it is outside the normal in-game loading requirement.

## Bounded storage

Use one dedicated directory per opted-in playthrough. Keep the current committed
generation and at most three previous verified generations. Cap the total owned
directory at 64 MiB, including staging, manifests and pending records. Before a
copy, account for its temporary space too. If the current save does not fit,
stop with a storage error; do not remove the last good generation to make room.

Copy only the selected save and the small mod state needed for the same
generation. Never copy a game directory, `_scratch`, build trees or all profiles.
Rotate only exact files recorded as owned by this feature, after verification.
Do not treat Rockstar's `.bak` as independent recovery: a prior local fault left
the autosave and its `.bak` byte-identical after progression was damaged.

## Implementation order and required proof

1. Add a read-only observer for the existing save owner. Prove request identity,
   completion/error identity, selected profile/slot, and character/replay guards
   on a prepared disposable save. No forced save or load interception yet.
2. Implement generation storage and crash recovery against temporary fixtures.
   Inject failures before/after every write, rename and acknowledgement. Prove
   that restart selects either the old committed generation or the complete new
   one, never a mixture. Test full disk, locked files and the 64 MiB limit.
3. Implement the sequence state machine with fake engine acknowledgements.
   Test delayed, duplicate, stale and missing acknowledgements; consequences
   arriving during a save; repeated load attempts; and profile changes.
4. Prove transaction identity and replay rules for each row above. Unknown
   transitions must remain explicitly incomplete, not silently discarded.
5. Prepare a disposable Story save and a visible read-only operation report.
   Test purchase, sale, consumption, bounty, death, arrest, mission retry,
   checkpoint, crash and recovery. Then review the concrete candidate before
   enabling it for a real playthrough, as the live issue requires.
6. Enable the normal-load policy only after save/recovery proof passes. Test all
   load entry points and prove that the development escape hatch is absent from
   the release binary. Deliver the selected build with its matching test steps.

Outstanding research: the exact request and completion hooks, all normal load
entry points, an idempotent consequence journal, and paired engine/mod-state
recovery. The source mapping above is evidence for the design, not runtime proof.
