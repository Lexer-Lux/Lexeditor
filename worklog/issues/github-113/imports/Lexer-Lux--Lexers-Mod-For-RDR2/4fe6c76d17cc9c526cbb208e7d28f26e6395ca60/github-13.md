# Worklog: GitHub issue 13

## Partial run and corrected follow-up

`StealthProbe-20260809-232527.csv` was an executed but aborted run. It completed
steps 0 through 24 and began step 25. It contained no combat, flee, or response
transition. Those null transitions were not accepted as hostile-detection
evidence because the isolated guard did not execute the authored Story enemy
detection state machine. In the visual trials, the observer also turned about
180 degrees from the player, so those trials were not valid hostile sight tests.

The run did provide usable player-state measurements. Labels were not trusted;
recorded state supplied the result:

- stand and crouch still: noise `0`;
- crouch-walk: median speed `1.38 m/s`, noise `0`;
- standing walk: median speed `1.38 m/s`, noise `1.83`;
- the step labelled run was the faster input: `4.47 m/s`, noise `10`;
- the step labelled sprint was the slower input: `2.85 m/s`, noise `5`.

The values confirmed the prior completed movement block. Movement, sound,
distance, and pulse steps were removed from the next run. The old sound-only
steps were not accepted because bearing and LOS did not hold the requested
behind-observer condition. The cover step was not accepted because it had no
ready gate. The lantern-off step was partial and the automatic belt lantern was
still on.

The follow-up was reduced to seven cover, lantern, and weather conditions.
Cover, lantern off/on, and clear-weather setup now wait without sampling until
F9. It logs the exact input values used by the standard Story detection helper,
including the three-state `CAN_PED_SEE_ENTITY` result and the immediate/lantern
branches from `gang1.c`, `func_2459`. It uses a neutral controlled observer; it
does not present synthetic guard combat as the result.

The follow-up ASI built successfully with SHA-256
`5269B4D62CDC2E8CE0DDF8B5B7CF86393E940D13BD41E282EFE319903E558A5E`.
It was not copied over the ASI loaded by the running RDR2 process. A hidden
standalone installer was queued to wait for RDR2 to close, then copy only
`StealthProbe.asi` and verify the installed hash.

## Failed replacement hostile-detection matrix

The previous probe did not answer the requested gameplay question. Its hostile
phase was invalid because the spawned observer remained under an indefinite
`TASK_STAND_STILL`, suppressing the autonomous AI response it claimed to test.
Geometry-native boundaries and player-noise values were supporting inputs, not
proof of when a hostile notices, investigates, or attacks.

`StealthProbe` was redesigned around synthetic hostile AI transitions. The
later partial run proved that this design still did not execute the authored
Story enemy detection state machine. Its transition claims were withdrawn.

This is built/static-tested probe work only. Until a complete in-game run is
analyzed, the practical stealth audit remains incomplete and #13 remains
`actionable`; #19 does not have sufficient evidence for acceptance.

The three post-replacement files (`20260806-081726`, `084211`, and `084427`)
contained only `probe_loaded`: no F7/arming event, observer verification, trial
sample, or completion event occurred. The game-root ASI was absent by the next
recorded launch. These files prove the replacement matrix was not executed and
contain no stealth result. The probe now emits five-second idle heartbeats that
explicitly distinguish not-executed, failed, and complete states.

The heartbeat build was installed and hash-verified on 2026-08-09:
`512EC04AE6E82562E4A41BBDCD8BA1356458D503E481ECF23B614E662979E621`.

## Controlled stealth-system audit

The self-verifying free-roam observer probe completed two sessions:

- `StealthProbe-20260728-055229.csv`: complete through
  `C04_HOSTILE_HIDDEN`; 7,847 observer samples across the 34-step run.
- `StealthProbe-20260806-061137.csv`: complete through
  `B09_HOLSTER_SETTLE`; 2,714 observer samples across the 16-step follow-up.

The first run supplied distance, broad-angle, seeing-range override, pulse and
synthetic-hostility results. Its player-action block was invalid because the
HUD instructions were not visible and the recorded player never moved,
crouched, drew or aimed. The second run visibly presented the instructions and
recorded the requested player states, so it superseded only that invalid block
and added the 35-55 degree fine-angle sweep.

### Results

- Observer render verification passed before both runs.
- At 15 m, `IS_TARGET_PED_IN_PERCEPTION_AREA` was true through 55 degrees and
  false at 60 degrees; head-on it was true through 60 m and false at 75 m.
- A per-ped 5 m seeing-range override made the perception-area result false at
  15 m; restoring 60 m made it true.
- 150 ms facing pulses were visible in the perception-area result, with no
  accumulating or decaying motivation value.
- `CAN_PED_SEE_ENTITY` ignored rear-facing geometry and
  `CAN_PED_SEE_PED_CACHED` persisted across changes. Neither was a complete
  immediate NPC-detection signal.
- The run was on open ground. Foliage-check and non-foliage visibility matched
  in valid near-range samples, so actual foliage concealment was not tested.
- Suspicion, fear, anger and agitation were enabled but remained `0.000`.
  Synthetic hostility produced no combat, flee, witness or logged response.
- After trimming two seconds from player-instruction transitions:
  - stand still: median speed/noise `0.000 / 0.000`;
  - crouch still: `0.000 / 0.000`;
  - crouch-walk: `1.365 / 0.000`;
  - standing walk: `1.333 / 1.827`;
  - run: `3.955 / 5.000`;
  - sprint: `5.616 / 10.000`.
- The crouch flag was active during crouch steps while the separate stealth
  movement flag stayed false.
- Drawing a weapon caused no reaction. Aiming became active at 1,148 ms and
  fleeing began at 1,674 ms, a 526 ms delay; motivation and witness values
  stayed zero. Holstering cleared fleeing.

The settled interpretation was promoted to `codex/stealth-perception.md` and
the stale runtime-limit note about a failed observer workflow was replaced.
## Implemented rework

The audit showed that ordinary `DEFAULT_PERCEPTION` humans used
`TOD_MOD_DEFAULT`, whose sight curve remains `1.0` at every hour, even though
Rockstar ships a separate `TOD_MOD_PED` curve for human darkness response.
That PED curve was present but not referenced by any perception profile.

`MyOverhaul/ai/pedperception.meta` now routes only `DEFAULT_PERCEPTION` from
`TOD_MOD_DEFAULT` to `TOD_MOD_PED`. This makes the ordinary-human base seeing
range respond to time of day without a runtime ASI override:

- 23:00-04:59: `60 m * 0.50 = 30 m`;
- 05:00 and 22:00: `60 m * 0.75 = 45 m`;
- 06:00-21:59: `60 m * 1.00 = 60 m`.

Everything else stayed byte-for-byte vanilla. In particular, ordinary-human
hearing remains 60 m before weather/event processing; movement detection stays
200 ms; close standing/crouched velocity thresholds remain 2/3 m/s and far
thresholds remain 3/6 m/s. Law and Pinkerton profiles continue using their
already-existing `TOD_MOD_LAW` darkness curve. Animals and mission-authored
per-ped overrides were not changed.

This is a data-owned stealth rework, deliberately not a global runtime range
writer: mission scripts can still apply their own per-ped ranges, and there is
no unsafe restore-to-guessed-baseline path. Crouch/stealth/prone continue using
the engine's separate stance, velocity and noise inputs proven by the probe.

Static verification:

- `python tools/reverse-engineering/verify_stealth_rework_issue_13.py`
  passed. It parsed both XML files, proved the modded file differs from vanilla
  by exactly the one intended modifier hash, checked the 24-hour PED curve, and
  locked the human thresholds/ranges plus unchanged law routing.

Integration still needs to register
`common:/data/pedperception.meta -> ai/pedperception.meta` in the shared
MyOverhaul install descriptor, then install it. Runtime acceptance is a
day/night hostile-observer comparison; this source-only handoff is not yet a
`test me` state.
