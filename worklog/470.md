# #470 — Chocobo whistle should bring the chocobo to you and mount it

## State (2026-09-23 impl/ff7r2-actionables pass)

- No agent-side implementation slice remains. The Data Map row
  `End/Content/DataObject/Resident/ResidentParameter.uasset (#470)` is
  `not-integrated` with no control, and the service exposes no chocobo
  route. This is deliberate: the callable sequence is unproved.
- Public evidence already recorded in `plugins/ff7r2/server.py`: constants
  `CallChocoboAtFieldActionDistanceParamRatio0/1`, whistle/chocobo
  identities, plus generated-SDK seams (`AEndLocationVolume.bDisableChocoboRide`,
  `UEndEnvQueryTest_IsDisabledChocoboRide`,
  `UEndEnvQueryContext_LastEnableChocoboRideLocation`,
  `FEndBehaviorChocoboRideOnExtraAction`).
- Verification this pass: `tests/test_ff7r2_dataobject.py`,
  `test_ff7r2_server.py`, `test_ff7r2_packaging.py`,
  `test_ff7r2_shader_injector.py` — 66 passed; managed service smoke
  passed; plugin descriptor valid. No source changes; nothing to regress.

## Blocker (needs installed game, Lexer)

- Prove the callable safe-teleport plus immediate-mount sequence.
- Distance-ratio semantics and valid ranges for the two ratio params.
- Ride-legality predicate and vanilla fallback where riding is disallowed.
- Safe-placement rule (wall, slope, water). Dismount stays untouched.

Stays `actionable`. No speculative control added.
