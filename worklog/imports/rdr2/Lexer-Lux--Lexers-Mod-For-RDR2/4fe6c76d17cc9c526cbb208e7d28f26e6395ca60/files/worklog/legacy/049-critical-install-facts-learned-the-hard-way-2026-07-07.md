# Worklog: 049 Critical Install Facts Learned The Hard Way 2026 07 07

## CRITICAL INSTALL FACTS (learned the hard way 2026-07-07)

- **Always copy .asi to the game ROOT immediately when built** — do NOT gate on
  "game not running". Unloaded .asi files aren't locked; a running game only
  locks the ones it loaded at startup. Gating caused GameplayTweaks to never
  install for days. (If the CURRENT .asi is loaded, its file is locked — that's
  the only real block, e.g. CoreVignetteRamp v2 while the game runs.)
- **.asi loads only at game STARTUP** — the user must fully restart RDR2 for any
  .asi change to take effect.
- If the currently loaded ASI is locked, Windows permits a reliable next-start
  install: rename it to a suffix that does not end in `.asi` (for example
  `GameplayTweaks.asi.loaded`), then copy the new build to the canonical `.asi`
  filename. The running process keeps its already mapped old image; the next
  launch loads only the new canonical file. This was verified on 2026-07-14.
- On 2026-07-14 the installed MyOverhaul catalog had become stale relative to
  the editor source. All 76 install.xml mappings and strings.gxt2 were
  revalidated and hash-synced while the game was closed. When diagnosing an
  editor/game discrepancy, compare source/install hashes before reasoning from
  the editor display.
- Lexer's normal-play preference is vanilla-ish data: `MyOverhaul` should be
  absent/disabled except during explicit test sessions. For the 2026-07-14 test
  it is synced to `<game>\lml\MyOverhaul` with all 76 install.xml mappings hash-
  verified, `Overwrite=true`, and exactly one final load-order entry so its
  current crime/loot configuration wins `Crime Tweaks`/`LexNoAutoAmmo` during
  the test. Easy uninstall/return to normal is deleting or moving that single
  folder; the prior manager state is backed up as
  `<game>\lml\mods.xml.before-MyOverhaul-test.xml`.
- 2026-07-15 direct-edit workflow: `<game>\lml\MyOverhaul` is a Windows
  directory junction targeting `C:\RDR2Mod\MyOverhaul`. LEXEDITOR therefore
  edits the exact files LML loads on the next game launch; do not copy the mod
  directory after ordinary editor saves. The previous physical install is
  preserved beside the junction as `lml\MyOverhaul.before-junction-<timestamp>`.
  Data replacements are startup-loaded and do not hot-reload. This temporarily
  supersedes the normal vanilla-ish preference at Lexer's explicit request.
- Dropped per Lexer 2026-07-07: TODO #2 (skills), #3 (weight/mounted drain),
  and #5 (deadeye regen). TODO #1 was later revived as the NoReserveCores
  enforcement build and is in testing. GameplayTweaks also now owns CoreClock,
  wagon cores, train tracking, collectible mapping, stamina tuning, and minimap
  zoom. #6 skip-movies remains unresolved; #7 animal density is off by default.
- TODO #60's Series/Parallel conversion failed in game and is DROPPED. Separate
  roots prove the existing strand page enumerates roots sharing its `menuLink`;
  they do not prove that a new top-level pause-menu strand/menuLink can be added.
- Story Mode's `player_camp` script calculates a valid camp coordinate around
  the player (`func_102`) and persists the current camp in globals; it is not
  established as a finite enumerable list of fixed campsite records. Persistent
  multi-camp mapping/nearest-death-respawn therefore requires our own saved
  coordinates and runtime lifecycle handling rather than exposing a static list.
- **Vignette stays the texture/.ytd (DRAW_SPRITE) route — Lexer rejected the
  timecycle-modifier compromise as substandard.** The .ytd bake + skip-movies
  boot-config extraction both need an OpenIV session; do them next time Lexer
  frees the machine. When asking him to finish/compile for testing, remind him
  up front what window I need (game closed / restart). See memory
  rdr2-build-test-workflow.

- 2026-07-12: `PlayerRPGEmptyCoreStamina` still visibly pulses under v5's
  non-expiring potency path. This proves the cycle is intrinsic to the effect
  asset; strength/potency cannot freeze it. Disabling that layer then left
  Stamina with no effect, while the empty-core Health asset also disappeared
  when sourced from the outer bar. The 2026-07-15 test build uses one shared
  `PlayerRPGCore` container, applies the three potency channels without
  per-controller overwrites, and logs measured fullness/strength/running state
  to `CoreVignetteRamp.log`. The retest still produced a sinusoidal stamina
  cycle and brief lifecycle flickers, so all three channels are disabled in
  the test INI rather than leaving an unplayable effect active. Do not claim a
  smooth ramp works until a non-pulsing asset or faithful recreation is proven.
- Rockstar item/localization text does not understand GTA shorthand color
  tags such as `~g~` and `~r~`; those render literally. Testing also proved
  named `~COLOR_*~` and reset `~s~` tokens render literally in item-wheel
  descriptions even though other RDR2 UI surfaces support them. LEXEDITOR now
  strips color/reset markup from item descriptions while preserving `~n~`.

