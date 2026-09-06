# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356300299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/172

Created: 2026-08-06T03:15:02Z; updated: 2026-09-05T06:58:41Z

Exact metadata: [source record](sources/issue-5356300299-a66c9674714f52342a45051642e743e5dce2609ff6f6d1f29ac6149d35b54ff7.json).

When death respawn redirects Arthur to the nearest activated authored campsite, the destination must be a safe ground position beside the campfire—not the campsite origin/on top of the fire.

Acceptance:
- Respawning at every activated campsite places Arthur beside the fire with safe clearance.
- The placement uses the campsite's heading so the offset is stable and predictable.
- Arthur must not intersect the fire, campsite props, steep/invalid ground, or immediately take fire damage.
- Existing nearest-activated-campsite selection and camp materialization behavior remain unchanged.
- Build and install for in-game confirmation.

## issue 5356300299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/172

Created: 2026-08-06T03:15:02Z; updated: 2026-09-06T12:54:53Z

Exact metadata: [source record](sources/issue-5356300299-19e26f27d88cf2879b8b5ec52201ea17180343a12c04e6d582781cc69ae8491b.json).

Respawn beside the nearest activated campfire, never on its flames or inside its props.

**Status: A safe-placement build was queued, but installation was not confirmed.** Verify the current combined campsite build and prepare a known activated-camp test first. Later respawn work in #244 is also awaiting installation.

## comment 5550128521 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/172#issuecomment-5550128521

Created: 2026-08-06T03:18:52Z; updated: 2026-08-06T03:18:52Z

Exact metadata: [source record](sources/comment-5550128521-d779a6812c7a4f8a6c651a54ff6678b24f986e65f1beb3db23a22544c3909dba.json).

Implemented locally. Root cause confirmed from Rockstar's `player_camp.c`: the saved campsite coordinate is exactly the `P_CAMPFIRE02X_COMBO` origin, and the respawn loop reused it as Arthur's destination.

The respawn loop now chooses heading-relative ground 4–5 m beside the fire, validates slope/water/height and safe-coordinate proximity, requires at least 3 m fire clearance, and has no fallback to the fire origin. Build passed (only the two pre-existing C4838 warnings), SHA-256 `415DF8F5BD02DA8EC681D6F4774053A6468F07ECB8FBE721EB31CE08B6E64A76`.

RDR2 is currently running, so the existing hidden install-on-exit watcher will install and hash-verify it after exit. Keeping `actionable` until installation completes; then it should move to `test me` for an in-game death-respawn check.
