# GitHub #152 — Respawning

## Recurrence audit before implementation

- **Primary evidence/reference:** the live issue reports that dying roughly 30
  metres from an activated campfire still produced the ordinary nearby Rockstar
  spawn. The owning runtime path is the campsite death/respawn block in
  `GameplayTweaks/script.cpp`; campsite activation persistence is owned by
  `GameplayTweaks/modules/world_economy.cpp`; Rockstar's authoritative camp and
  death transitions must be resolved from `player_camp.c` and the Story death
  scripts before changing behavior. Prior attempts are preserved in
  `github-73.md`, `todo-59.md`, `github-122.md`, and the campsite section of
  `github-99.md`.
- **Sanctioned path:** capture a specific activated campsite on the real death
  transition, persist that selection through Rockstar's death sequence, wait
  for the selected destination to stream, then perform one hidden coordinate
  write to a terrain-validated offset beside the fire. Do not fight Rockstar's
  placement per frame and do not fall back to the fire origin.
- **Execution proof:** the issue-local diagnostic must preserve prior evidence,
  emit an idle heartbeat, and record the selected campsite identity/position,
  activation state, death and death-sequence edges, safe-position resolution,
  the single teleport attempt, and a bounded position/collision readback. A
  call-site line alone is not proof of a respawn.
- **Rendered/player-visible acceptance:** after an activated campfire has been
  selected, a real death must place Arthur beside that exact fire rather than
  at Rockstar's nearby spawn, with no long camera flight and no placement in
  flames/water. With no activated campsite, vanilla respawn must remain intact.
- **Per-frame mutation audit:** campsite scanning and diagnostics must be
  bounded. Streaming requests may repeat only during the finite post-death
  window; coordinate mutation must occur once per death; readback must have a
  fixed timeout/cadence; file output must be transition/heartbeat based rather
  than per frame.

