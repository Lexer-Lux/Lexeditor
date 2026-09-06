# Final road-speed control removal — 2026-09-06

The latest explicit user decision supersedes the rejected +15% road-speed extension: provide a useful increase above the native cap or remove the ineffective speed controls. The runtime source still contained both speed readers/writers, while current Lexeditor master had already lost the human metadata but still exposed the horse row.

This public repair removes the remaining `HorseStamina|RoadSpeedMultiplier` label, numeric range and help entry. `HumanMovement|RoadSpeedMultiplier` was already absent here. The companion runtime PR removes both rejected speed settings/readers/writers and the obsolete #71 speed-only INI fragment while retaining exact-road sampling and both `RoadDrainMultiplier` stamina benefits.

No stamina rates are changed by this presentation cleanup. Runtime build/game acceptance is tracked separately; this note does not claim an installation.
