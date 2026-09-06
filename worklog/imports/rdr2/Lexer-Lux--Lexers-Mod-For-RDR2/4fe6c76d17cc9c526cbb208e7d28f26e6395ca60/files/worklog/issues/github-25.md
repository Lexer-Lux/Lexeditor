# Worklog: Github 25

## GitHub #25 core XP gain toggle — 2026-08-05

Rockstar's generic RPG award path adds points to `Global_40.f_11095.f_11[0..2]`,
then applies those totals through `SET_ATTRIBUTE_POINTS`; its rank thresholds
are 0/50/100/200/350/550/800/1100. GameplayTweaks now reads
`[CoreXPGain] Enabled`, default 0. Once the player is alive, unfaded and under
player control it captures the loaded Health/Stamina/Dead Eye base ranks. Any
later increase is restored to that ceiling with `SET_ATTRIBUTE_BASE_RANK`.
This deliberately controls the maximum-core progression layer instead of the
current core point store, so existing ranks and CoreClock fill/drain survive.

## Regression: CoreClock overwrote saved progression — 2026-08-05

The same-day CoreClock experiment incorrectly routed current 0..100 core-fill
values through `SET_ATTRIBUTE_POINTS` before `_SET_ATTRIBUTE_CORE_VALUE`.
Attribute points are permanent Health/Stamina/Dead Eye progression, so restarting
with CoreClock enabled replaced the saved maxima: Dead Eye fell to zero and
Health/Stamina to approximately 25. The autosave and its `.bak` were already
byte-identical after the fault and could not recover the former ranks.

The points path was removed from `SET_CORE`; player and horse current-core writes
now use `_SET_ATTRIBUTE_CORE_VALUE` only. Both source and installed INIs set
`[CoreClock] WriteMode=0` as an additional guard. The corrected ASI built and was
installed with SHA-256
`AB788122B96EE75544B0BE1A41D5022383F323AB367FA21A10A1974C26911390`.

Exact recovery does not require guessing the damaged rings. Rockstar retains
cumulative XP independently at `Global_40.f_11095.f_11[0..2]`; thresholds are
0/50/100/200/350/550/800/1100. A one-time guarded repair now reads those three
totals, logs existing points/base/bonus ranks, reapplies the exact totals with
`SET_ATTRIBUTE_POINTS`, verifies all three readbacks, and deletes
`GameplayTweaks.repair-core-ranks.once` only on success. The flag is installed
for the next save load. Runtime success is recorded in
`GameplayTweaks.core-rank-repair.log` and remains to be observed.

The first recovery attempt proved the inferred Health global offset was wrong.
Its log captured all three ped values before writing: Health/Stamina/Dead Eye
were each exactly 1100 points, base rank 7. The inferred Health float was a
positive subnormal (`3.22299e-44`), was incorrectly accepted as zero, and the
repair itself reduced Health from 1100 to 0. Stamina and Dead Eye remained at
1100. Verification failed and retained the flag as designed; the bad flag was
then removed before another restart.

Health recovery is therefore no longer inferred. A standalone one-use
`CoreRankRepair.asi` restores attribute 0 only to the logged pre-damage value
1100, verifies the points readback, logs base/bonus rank before and after, and
deletes its trigger only on success. It is built with SHA-256
`6BAA3E332C090AFA91815E846E2C64F26BFB156825D226A892B3FA8E4A5F7858` and a
hidden watcher installs it after the current RDR2 process exits. The main-source
recovery path now refuses to act without an explicit exact-values file.

The ASI built successfully with the two pre-existing C4838 warnings and was
installed while the game was closed. Source and installed ASI SHA-256:
`E993F7379FF84EC70A128CE3D7C3612597A032EF7A80653B30EBEF5C416B83F5`.
Source and installed INI SHA-256:
`F15BF0B88E7392B5AEDB011EEEB44D77C591FD2831EA82B3C3A36965356241D1`.
Runtime blocking remains unverified pending an activity that normally awards
core XP.

