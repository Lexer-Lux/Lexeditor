# Worklog: Github 73

## GitHub #73 campsite respawn on fire — 2026-08-05

Rockstar's `player_camp.c` proved that the explicit camp coordinate is also the
exact coordinate where `P_CAMPFIRE02X_COMBO` is created. GameplayTweaks used
that same `Campsite.pos` both to materialize the camp and to respawn Arthur, so
being placed physically on the fire was deterministic rather than a random bad
spawn.

Added a separate campsite respawn-position resolver. It tests eight positions
4–5 metres around the fire in campsite-heading space, requires dry ground with
the same slope limit used when authoring a campsite, rejects large height jumps,
and accepts only safe-coordinate results that remain at least three metres from
the fire. The terrain-validated candidate remains usable while navmesh discovery
is streaming, but there is deliberately no fallback to `Campsite.pos`: failure
leaves Arthur at Rockstar's vanilla respawn instead of ever putting him in the
flames. The re-assert window now measures success against that safe position.

GameplayTweaks built successfully with the two pre-existing C4838 warnings. The
745472-byte ASI hashes
`415DF8F5BD02DA8EC681D6F4774053A6468F07ECB8FBE721EB31CE08B6E64A76`.
RDR2 was running and the existing hidden install-on-exit watcher remains active;
the issue stays `actionable` until that watcher installs and hash-verifies this
build, then it needs the in-game death-respawn confirmation.

