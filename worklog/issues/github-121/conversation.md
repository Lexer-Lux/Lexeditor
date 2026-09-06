# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356288830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/121

Created: 2026-08-06T01:58:00Z; updated: 2026-09-05T06:55:56Z

Exact metadata: [source record](sources/issue-5356288830-5f0e7de11ec70930cda425fa3263f8d45325913fe010a6189f22d5773faf4bc0.json).

DARK SOULS-STYLE CONTINUOUS SAVING / NO MANUAL LOADING — you can't reload
     an earlier save during normal play, and everything meaningful persists
     automatically so quitting can't erase consequences: money, inventory,
     health/cores, crime/bounty/honor, deaths and lost money, challenge
     progress, world pickups, merchants, camps. Must handle death, arrest,
     mission failure, crashes, mission checkpoints and save-slot migration
     without corrupting a save or trapping me in a broken state. Keep a debug
     escape hatch outside normal play, but no player-facing undo loop.
^ maybe debug escape hatch = in Lexer-Lux/Lexeditor#120 devmode only?

## issue 5356288830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/121

Created: 2026-08-06T01:58:00Z; updated: 2026-09-06T12:46:36Z

Exact metadata: [source record](sources/issue-5356288830-cbf755fb49d8dc2d3652dea043f4663838eb6508448ca7177a3fbb5478eb1daf.json).

Persist meaningful consequences automatically and remove normal manual-loading undo loops. Keep a development-only recovery escape hatch.

**Status: Not implemented.** Save safety, crashes, death, arrests, mission checkpoints and recovery need a concrete design first. Prepare that design before asking you to approve changes to real saves.

## issue 5356288830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/121

Created: 2026-08-06T01:58:00Z; updated: 2026-09-06T12:46:36Z

Exact metadata: [source record](sources/issue-5356288830-efcfc4fd1df0d5ac13c1475e6fa0654b373f0a6f8fbac45a4a3f0049c160a9f8.json).

Persist meaningful consequences automatically and remove normal manual-loading undo loops. Keep a development-only recovery escape hatch.

**Status: Not implemented.** Save safety, crashes, death, arrests, mission checkpoints and recovery need a concrete design first. Prepare that design before asking you to approve changes to real saves.
