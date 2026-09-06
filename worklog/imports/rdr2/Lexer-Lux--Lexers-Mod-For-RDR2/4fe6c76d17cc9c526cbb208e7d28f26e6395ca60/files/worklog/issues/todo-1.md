# Worklog: Todo 1

## #1 horse stamina reserve boundary — 2026-08-05

Lexer's completed reserve probe showed the remaining failure precisely. The horse
was at 21.8163/140 Stamina with core/protected core 30, then one second later at
7.8163/100 with core 20 while the protected value remained 30. Detection and
baseline retention were working; exhaustion was not latched at the already-known
16% visual floor. The code waited for a subsequent core drop (or a 1% bar) before
disabling drain, so the core necessarily acted as the backup bar first.

Changed the horse path to latch exhaustion immediately upon entering the visual
floor. While latched, Rockstar's horse depletion multiplier is zero and the
custom net-rate controller clamps negative rates to zero; positive recovery is
still allowed. The latch clears only after sprint is released and the bar rises
above 18%, avoiding immediate release against the 16% floor. The existing
per-frame core restoration remains as a fallback for an engine spend that lands
during the boundary frame.

GameplayTweaks built successfully with the two pre-existing C4838 warnings. The
745472-byte ASI hashes
`32EC71B56444EB67FD18D0CD31152E7FB6AA4D941FAED463E3FFA7EF77684649`.
RDR2 was running, so `Install-When-RDR2-Closes.ps1` was started hidden to install
and hash-verify the build automatically after exit. A complete restart is still
the runtime acceptance boundary.

## #1 horse Health core reserve — 2026-08-05

Lexer reported this before receiving the horse-Stamina boundary build; the
Stamina fix did not cover Health. The existing damage probe nevertheless already
contained the cause: horse Health fell from 132/140 to 32/140 while its core
remained 82, then max Health changed from 140 to 120 while the core still read
82. A reserve tick happened and was restored between one-second samples, but
the restoration used the generic player `SET_CORE` path, including
`SET_ATTRIBUTE_POINTS`. Rockstar's `player_horse.c` func_644 uses only
`_SET_ATTRIBUTE_CORE_VALUE` for horse cores. The progression-points write was
mutating the mount's maximum outer bar, making the attempted protection itself
look and behave like reserve consumption.

Added `SET_HORSE_CORE` using Rockstar's direct setter and routed all owned-mount
Stamina/Health pins plus wagon-team core drains through it. Horse Health no
longer waits alive below the outer-bar boundary: for ordinary horse max Health
above 100, native Health 100 is the empty outer bar, the protected core is
restored if necessary, and the horse dies immediately. A legacy/corrupted horse
whose max is already 100 uses zero as its boundary so it is not killed while
nominally full.

GameplayTweaks built successfully with the two pre-existing C4838 warnings. The
747520-byte ASI hashes
`22A250B8E9B3DBD5678413D6348E94D40769E5E527A592276698F233F4E16482`.
RDR2 was running; corrected watcher PID 406808 will install/hash-verify this
build on exit while also removing CoreVignetteRamp from the loader path.

