# GitHub #116 — campsite removal and accidental F2 relocation

The live authored camp list proved the Valentine campsite still existed. The
removal path measured Arthur only against the saved campfire origin with an
eight-metre cutoff, even though the authored rest/tent positions can place him
outside that radius. The same mismatch let a tap pass placement validation and
create another camp in the physical layout.

Removal and duplicate prevention now share a 30-metre authored-camp footprint.
The action still requires the deliberate 800 ms F3 hold; tapping F3 inside an
existing camp is rejected rather than layering another camp over it.

The live `campsites.csv` contained 14 sites and no pair within 120 metres, so a
30-metre exclusion did not merge or make any existing authored sites
unreachable. The live campsite log contained 2,991 historical lines, including
2,414 launches for site 0 and 514 for site 1 with consecutive thread IDs. A
short-lived or rejected `player_camp` instance was therefore being relaunched
every frame. Materialization now deduplicates pending cleanup, retries a
successful launch no sooner than five seconds later, and backs off a failed
start for one second. The session log is truncated on load and records the site
count, launch target/attempt, and removal distance so the next runtime test is
not contaminated by old sessions.

Deleting a site now also repairs the requested-site and launch-target indices,
including clearing a deleted pending request. This prevents an erased vector
index from being reused by the asynchronous camp cleanup/materialization path.

The live F2 trace identified two accidental relocations: Flora of America Card
9 was moved exactly to the campsite coordinate, and Davey Callander was later
moved 94 metres. Their last override rows were removed from the game-root
fixup file. The current file retains Flora Card 9's preceding override at
`-1851.299,-464.341` and contains no Davey override, so last-row-wins lookup
will restore the preceding/base locations after restart.

Static verification passed with
`python tools/reverse-engineering/verify_campsites_issue_116.py`: both campsite
operations use the shared radius, the hold/tap split remains guarded, launch
backoff and diagnostics are present, all 14 live sites are mutually safe at the
new radius, and neither accidental F2 row remains.

Runtime acceptance still required after integration deployment:

- At the Valentine tent/rest position, holding F3 for 800 ms removes the saved
  campsite and its physical camp.
- Tapping F3 anywhere within 30 metres of that site's saved fire origin does
  not create a duplicate.
- The new session log reports `loaded-sites=14` (or the then-current count) and
  does not show consecutive per-frame `player_camp` launches.
- After restart, Flora of America Card 9 uses its preceding location and Davey
  Callander uses the base/prior location rather than either accidental F2 move.

The combined build and next game-root deployment remain integration-owned.

## 2026-08-10 distant respawn streaming correction

The respawn loop requested collision at the chosen campsite but ended immediately
when `campsiteRespawnPosition` returned false on that same first frame. Distant
campsites are not normally streamed then, so this bypassed the intended 15-second
retry window. The loop now retries terrain/navmesh resolution through the full
window and only completes on verified placement or genuine timeout. Static
verification rejects the old first-false abort condition.
