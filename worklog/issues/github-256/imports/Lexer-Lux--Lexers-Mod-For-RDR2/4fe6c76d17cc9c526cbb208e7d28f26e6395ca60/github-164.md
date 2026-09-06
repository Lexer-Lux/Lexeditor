# GitHub #164 - Tear Down Campfire Option Still Exists

## 2026-08-10 recurrence audit before source edits

- **Requested result:** while near or sitting at a free-roam authored player
  camp, neither Tear Down Camp prompt may appear or execute. `Leave Fire` must
  remain usable.
- **Concrete current defects:** `ownedCampActive` was derived only from a saved
  campsite row within 30 m, even though the F3 path already proved a physical
  `P_CAMPFIRE02X_COMBO` plus live `player_camp` refs can outlive its row/transient
  association. The exact prompt was also hidden/enabled only on the 250 ms
  readback cadence, so Story could re-enable it for many intervening frames.
- **Sanctioned path:** outside missions, protect either a saved footprint or the
  exact player-camp fire within 10 m with a live `player_camp` script reference.
  Acquire only the registry prompt owned by `player_camp`, with constructor
  context/action/hold fields matching its authored teardown prompt. Hide and
  disable that exact cached handle every protected frame. Disable only the
  dedicated `INPUT_PCAMP_TEARDWN` action. Never disable shared
  `INPUT_CONTEXT_B`, which owns Leave Fire too.
- **Runtime boundary:** static fields and setter readbacks cannot prove the
  prompt is absent. Lexer must verify both standing-near and sitting-at-camp
  views, hold F for Leave Fire, and confirm no teardown/cutscene occurs.

The #164, #1, #116 and #163 campfire verifiers passed together. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; standing/sitting prompt absence and Leave Fire remain `test me`.

## 2026-08-10 returned test

The first repair acquired only the standing teardown record: priority 0,
transport 1. Sitting creates a second exact `player_camp` hold prompt with the
same Context-B control but priority 2 and transport 0. `func_758` only changes
its displayed tag; `INPUT_PCAMP_TEARDWN` was not a separate control action, so
disabling that hash did nothing. The policy now acquires and suppresses both
exact long-hold handles. The short Leave record has priority 1 and remains
untouched.

## 2026-08-11 exact cache-ownership repair

The latest installed log did not contain a teardown-guard acquisition. That
session had an inactive site, no physical fire and one stale `player_camp`
reference, which the existing orphan cleanup reduced to zero. It therefore did
not exercise either active-camp prompt and could not establish that the current
two-handle repair ran or failed.

The source audit found one remaining concrete defect. A cached UiPrompt handle
was checked only for native validity. Rockstar can free a registry record and
reuse its slot or handle, so the cache could later hide an unrelated valid
prompt. The repair now retains the exact owner thread and rechecks allocation,
priority, transport, handle, Context-B action and owner-thread ID in the same
registry slot before every write. A changed record is released and reacquired;
it is never suppressed through the stale cache.

The primary Story evidence remained:

- ambient teardown is priority 0, transport 1 and Context-B;
- short `Leave` is priority 1, transport 0 and Context-B;
- the seated long hold is priority 2, transport 0 and Context-B;
- `INPUT_PCAMP_TEARDWN` is only the seated prompt tag. It is not its control
  action.

The two exact long-hold handles remain the only mutation targets. The repair did
not disable or zero Context-B and did not touch the priority-1 short `Leave`
record. A two-second heartbeat now reports each exact handle as missing or gives
its slot, handle, validity, enabled state and active state. The enabled readback
remains an explicit error if Rockstar restores it after the write. This makes a
future test distinguish non-execution, non-acquisition, stale ownership and a
failed disable instead of reporting only an intent.

The issue-local verifier passed together with #1 after this change. This was
static evidence only. Player-visible acceptance still requires all three
reported positions: standing at the fire, sitting at it, and the nearby
standalone prompt. Holding F must do nothing for teardown; tapping the valid
short `Leave` action must still work.
