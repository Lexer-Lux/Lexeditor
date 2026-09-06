# GitHub #24 - No surrender without paying a serious bounty

## Evidence

- `datasets/vanilla/crimeinformation.meta` is authoritative Story Mode crime
  data and gives every SP crime an explicit `Severity`. The supported definition
  of serious is therefore `Severity=High`, not a guessed bounty or wanted-level
  threshold.
- The SP High set (excluding the debug-only wanted-level crime) is assault,
  assault-law, trample, trample-law, bank robbery, jail break, kidnapping,
  kidnapping-law, resist arrest, law threatened, murder, murder-law,
  stagecoach robbery, train robbery, and accomplice.
- Decompiled `ambient_load.c` enumerates registered crimes at indices 0..23,
  treats struct slot 10 as the reported flag, and passes the first slot as the
  crime type. `_downloads/natives.json` identifies the native as
  `GET_PLAYER_REGISTERED_CRIME`.
- The native database identifies the exact current crime, crime dispatch,
  wanted score, bounty, registered-crime clear, wanted clear, arrest reset, and
  bounty-hunter pursuit clear calls. `law_arrest.c` confirms that the SP incident
  cleanup call is paired with law-state clearing.

## Implementation

- Added the unregistered `modules/serious_crime_payoff.cpp` feature module.
- During an active law incident containing a reported High-severity crime it
  disables only `INPUT_SURRENDER` and cancels the pre-busted arrest phase.
- A replacement prompt shows the exact full bounty. When unaffordable it stays
  visible but disabled and includes the exact shortfall; no law state changes.
- An affordable completed prompt first removes the exact cash amount. Only a
  successful transaction zeroes the current region bounty, clears the current
  crime/wanted state, and clears the active law/bounty-hunter pursuit.

## Integration and runtime boundary

- Integration must include the module and call
  `updateSeriousCrimePayoff(player, ped, inputOwned)` before other input owners.
- No ASI was built or installed in this worktree. Prompt coexistence, arrest
  interruption timing, the registered-crime lifetime during a later
  bounty-hunter encounter, and pursuit cleanup require in-game confirmation.
