# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356303310 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/186

Created: 2026-08-06T03:57:07Z; updated: 2026-09-05T06:59:23Z

Exact metadata: [source record](sources/issue-5356303310-05b0d110c274d28bb25176069bacf1e260948dd201df3b151c28254f25404cec.json).

ALL of the icons we add -- and this seems to be the case for other mods, too -- are visible on the map from game start. The even reveal the area around them. I don't think that's how vanilla game icons work, though. But how do they? Will I have to check myself?

## issue 5356303310 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/186

Created: 2026-08-06T03:57:07Z; updated: 2026-09-06T12:55:17Z

Exact metadata: [source record](sources/issue-5356303310-14d66869fb75c80dd08889466e5042b6dd770bca7f451ce08b629c74dfa20d1a.json).

**Status: Research complete; marker discovery is not implemented.** Proposed behavior: show a custom marker only after nearby discovery, retain it afterward, and still respect quest/collection gates.

- [ ] Choose the discovery radius in metres and how existing saves should start: all custom markers undiscovered, or a defined set already known. For the latter, name which categories/locations should be imported as known.

## comment 5550131890 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/186#issuecomment-5550131890

Created: 2026-08-06T13:26:38Z; updated: 2026-08-06T13:26:38Z

Exact metadata: [source record](sources/comment-5550131890-ecd2a7c44d752ead4afc0f88e31a70c1d2cfb1bb44a16b90f6ae94e1bdce81a8.json).

Research result:

Vanilla does not create every icon as a startup coordinate blip. It has a separate discovery registry. `map_app_event_handler.c` suppresses labels/cards whose discovery hash is not active; discoverable and legendary scripts call `_MAP_DISCOVER_REGION` after their gameplay trigger, while some story/state unlocks use `_MAP_DISCOVERY_SET_ENABLED`.

Fog of war is separate. Story scripts explicitly use minimap FOW reveal/reset/update natives. Our mod calls none of them; it directly creates every eligible coordinate blip during startup/refresh. Those live remote blips therefore render immediately, and their apparent parchment clearing is a consequence of remote blips rather than an explicit fog-reveal call. No native was found that asks whether arbitrary XYZ is already revealed.

Recommended future implementation: persist a `discovered` bit per mod-authored static marker and do not create its blip until Arthur enters a configurable 2D discovery radius. Once discovered, recreate it on later sessions until collected/otherwise gated. Keep mission/quest gates in addition. A migration policy is still a user decision: existing saves can start undiscovered or import some prior knowledge. This avoids remote icon leakage and apparent fog holes without touching vanilla FOW. No implementation or relabeling was performed.
