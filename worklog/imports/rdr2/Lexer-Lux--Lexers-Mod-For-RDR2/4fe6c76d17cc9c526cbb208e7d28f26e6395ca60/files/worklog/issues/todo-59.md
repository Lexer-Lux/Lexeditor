# Worklog: Todo 59

## #59 death-cam coronas + campsite respawn — one root cause 2026-08-05

Both of Lexer's reports are the same defect: `IS_PLAYER_DEAD`
(`0x2E9C3FCB6798F397`) returns FALSE while the post-death sky cutscene is still
running. `[Campsites] RespawnWindowMs` already carried a comment admitting the
flag clears early; the 15 s re-assert window was the mitigation and it was
aimed at the wrong instant.

Consequences, both in the main loop:
- `updateProjectileVisibility` and `updateSpentCasings` were gated on `!dead`,
  so they resumed DURING the death cam. `updateProjectileVisibility` spawns a
  corona per shooting ped with `direction` computed toward `playerChest` — the
  killers keep firing at the corpse, so coronas streamed in from offscreen at
  his body. This is our own draw, not lost input; player-origin coronas require
  `IS_PED_SHOOTING(ped)`, which cannot fire with control locked. Nothing here
  supports the "controls unlocked" reading.
- the respawn window opened on the `!dead && wasDead` edge, i.e. at the START
  of the death cam. `placed` requires `PLAYER_CONTROL_ON` and `!SCREEN_FADED_OUT`,
  which are both false throughout the cutscene, so the 15 s expired mid-sequence
  and it took the `campMessage("...timed out...")` branch every time.

Fix: `dead` is now `PLAYER_DEAD(player) || IS_PED_DEAD_OR_DYING(ped, TRUE)`
(the ped's dying state outlasts the player flag), plus an `inDeathSequence`
latch raised on death and lowered only when alive AND `PLAYER_CONTROL_ON` AND
not faded. The two visual systems gate on the latch; the respawn window opens
on the latch's FALLING edge (`deathSequenceEnded`), so the 15 s now starts once
the game has finished placing him. `g_visibleProjectiles` is cleared on the
rising edge so in-flight tracers do not resume mid-air on fade-in.

The cash-drop / `nearestActivatedCampsite` capture stays on the rising `dead`
edge and is unchanged.

Built clean (two pre-existing C4838 warnings at script.cpp:1927, unrelated).
Installed to the game root, hash-verified
`5E995B40B1DF2B7DC869A99CEC259040222AAC9AE5846D71F36E50B34EF466BE`.
NOT confirmed in-game — the latch's lowering condition is the one assumption
that only a real death can validate.

