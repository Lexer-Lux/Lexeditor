# FF9 UI enhancements — 2026-09-06

Implemented on `codex/ff9-ui-bars-mognet-20260906`.

- Improved Interface: highlight the existing Mognet menu row when vanilla's Moogle choice mask indicates a deliverable-letter option for the current Moogle.
- XP Bars: independent tweak adding XP progress bars beneath post-battle party result blocks.
- HP/MP Bars: independent tweak adding red HP and blue MP bars below the existing battle HP/MP labels.

Automated verification:
- exact compile against pinned Memoria `v2025.07.04`
- 98 FF9 Python tests
- 11 FF9 JS controller tests
- feature UI patch idempotence
- deterministic committed runtime build

Status after merge: `untested` until live visual/in-game acceptance is performed.
