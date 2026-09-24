# #473 — Make the minimap zoom adjustable

## State (2026-09-23 impl/ff7r2-actionables pass)

- No agent-side implementation slice remains. The Data Map row
  `MapIconInfo.uasset + HUD package assets (#473)` is `not-integrated`
  with no control. No slider was invented: position/size/FOV evidence is
  not mislabeled as zoom.
- Public evidence already recorded in `plugins/ff7r2/server.py`: generated
  option categories `AreaNaviMapScale`, `LocationNaviMapScale`,
  `ZackNaviMapScale`; `UEndNaviMap.PixelPerCm`; Range entries with integer
  Min/Max; player-facing documentation confirming Rebirth already exposes
  separate world-navigation and specific-location scale controls where
  larger numbers show a wider area.
- Verification this pass: 66 passed across the four ff7r2 test files;
  managed service smoke passed; plugin descriptor valid. No source changes.

## Blocker (needs installed game, Lexer)

- Which NaviMapScale category binds to which persisted setting.
- Complete stored range, default (vanilla), and save/config location.
- Confirm the zoom applies to the world minimap and survives area
  changes and reloads before any control ships.

Stays `actionable`.
