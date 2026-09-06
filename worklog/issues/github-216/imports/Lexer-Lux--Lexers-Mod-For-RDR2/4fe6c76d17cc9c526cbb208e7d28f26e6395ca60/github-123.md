# GitHub #123 — Owned-horse restart persistence

## Requested

Stop the owned horse teleporting near the player when starting the game. Use Nexus mod 473 as decompiled reference evidence.

## Reference evidence

- Archive: `D:\Downloads\Horse Persistance-473-1-0-1618230943.rar`
- Extracted under `_analysis/reference-decompilation/horse-persistence-473/`.
- Nexus describes keeping the horse where it was left across game restarts and reports that hitched horses are unsupported.
- `horseTele.dat` is a 24-byte plain-text `x y z` record (`2432.77 -796.096 41.9121`). Binary string/cross-reference analysis confirms the ASI reads and writes that file as three floats. The reference has no horse identity or safety metadata.

## Implementation

- Added an independent implementation storing version, owned-horse model, position, and heading.
- Startup recovery never saves over the old location until restoration resolves.
- A matching owned horse is reasserted at the stored coordinate for a bounded ten-second startup window, then ordinary two-second persistence begins.
- Mounted-player, attached/hitched, dead, mission, invalid-position, missing-horse, and model-mismatch cases fail safely without moving anything.

## Verification remaining

- Static/build verification.
- In-game restart acceptance, including stable retrieval, replacement/death, missions, and hitched-horse safety.
