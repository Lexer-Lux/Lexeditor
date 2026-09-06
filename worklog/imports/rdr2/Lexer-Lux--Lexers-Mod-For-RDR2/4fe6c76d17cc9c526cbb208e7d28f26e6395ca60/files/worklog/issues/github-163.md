# GitHub #163 — Creating Campfires Is Still Broken

## Recurrence audit before code

`fuckups.txt` was read in full before this repair. The relevant recurrence
classes were: treating a log stage as the crash instruction without checking
the dispatch interval; preserving an unproven mutating native after repeated
runtime failures; and claiming a workflow fixed from static checks. The repair
therefore had to use the supplied image, both consecutive crash traces, the
last successful campsite event, and an authoritative alternative cleanup path.
No runtime acceptance is claimed here.

## Supplied failure and installed evidence

The issue image is the ScriptHook dialog:

`CORE: An exception occurred while executing 'GameplayTweaks.asi' (...), id 33`

The address shown in that dialog is the registered ASI entry address, not the
faulting instruction. The two consecutive sessions instead recorded the same
real engine exception:

`code=0xC0000005 address=RDR2.exe+0x25F799A`

The trace named `updateProjectileVisibility`, but that was a stale dispatcher
stage: no later stage marker existed before `updateCampsites`. In the second
session the exact final successful line was:

`[campsites] removal-hold ... nearest=15 distance=2.15612`

The next statement on that path was
`FORCE_CLEANUP_FOR_THREAD_WITH_THIS_ID(g_campThread, 555)`. Nothing after that
call logged. The same engine address failed in the preceding session. This is
direct repeated evidence against retaining the thread-id cleanup call.

## Repair

`GameplayTweaks/modules/world_economy.cpp` no longer calls the failing
thread-id cleanup native for campsite removal or site switching. It uses
Rockstar's separate `FORCE_CLEANUP_FOR_ALL_THREADS_WITH_THIS_NAME` native for
the exact `player_camp` owner. The module already refuses to start a camp while
any `player_camp` reference exists, so the name-addressed request cannot target
an unrelated second instance created by this system. The request retains flag
555, which `player_camp.c` checks at startup and routes through its authored
cleanup function before terminating.

The request logs the reason, tracked thread, active readback, and reference
count before mutation. `script.cpp` now sets the crash stage immediately before
`updateCampsites`, so any remaining camp failure cannot be mislabeled as the
earlier projectile update again.

## Static verification

Run:

`python tools/reverse-engineering/verify_campfire_crash_issue_163.py`

The verifier requires the exact NativeDB name/signature, the authoritative
`player_camp.c` 555 cleanup branch, the name-addressed call at both former crash
sites, absence of the thread-id cleanup call in the campsite module, and the
dedicated dispatcher stage.

## Runtime boundary

This remains `actionable` until the combined build is compiled and installed.
After installation it requires both tests before completion:

1. Hold F3 at a saved campsite: no ScriptHook exception, the saved row/blip is
   removed, and the physical camp exits.
2. Tap F3 on valid new ground: the saved row is added and the physical
   `P_CAMPFIRE02X_COMBO` appears; creation must not be inferred from a thread
   start or CSV write alone.

## 2026-08-10 returned F3 crash after the name-cleanup repair

The installed repair failed immediately on the next F3 hold. The preserved
trace recorded `code=0xC0000005`, `RDR2.exe+0x25F799A`, and the now-exact
`updateCampsites` stage. The last completed line was:

`removal-hold player=655.304,1408.84,182.413 sites=15 nearest=-1`

This disproves the name-cleanup call as the cause of this occurrence: with
`nearest=-1`, that branch was never entered. The next statement called
`campMessage("Stand at an authored campsite to remove it.")`. The new tooltip
wrapper had copied Story's two-struct layout but passed arbitrary English as a
raw pointer. Rockstar's `player_camp.c` supplies either a real GXT label or a
value returned by `_CREATE_VAR_STRING`; the SDK likewise documents var-string
construction for display text. The wrapper now creates a `LITERAL_STRING`
var-string, refuses a null result, and gives the feed call its own crash stage.

The event also proved the matching failure persisted. The nearest saved
Valentine row was about 159 metres from Arthur's reported live camp position,
outside the 30-metre saved-origin footprint. F3 now additionally recognizes
only the exact `P_CAMPFIRE02X_COMBO` model within 10 metres while an exact
`player_camp` script reference is live. If the transient materialized-row index
survived, that row is removed normally. If it did not, the exact physical
player-camp owner is cleaned up but no unrelated saved coordinate is guessed
or erased; the log states `savedRow=unchanged`.

This repair is not runtime-accepted. It must compile and install, then the same
F3 hold must prove no exception, the physical camp disappears, and the log
must show whether a saved row was associated or deliberately preserved.
