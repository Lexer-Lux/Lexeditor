# GitHub #44 - Gunslinger Quest Map Reveal

## 2026-08-05 implementation

Implemented the reveal as four ASI-owned presentation blips without changing
Rockstar's stranger-mission globals, photograph state, or mission progression.

Evidence from the shipped Story Mode scripts:

- `rcm_callaway1.c` `func_97` grants all four photograph documents together at
  the end of the introductory Calloway mission:
  `DOCUMENT_GUNSLINGER_{1,2,3,5}_NOTE`.
- `init_all_sp.c` registers the four target records and their exact data:
  record 84 / `RGUN11` / Emmet Granger at `-62.69012,-404.3738,69.91233` with
  `BLIP_RC_GUNSLINGER_1`; record 86 / `RGUN2` / Flaco Hernandez at
  `-967.5845,2181.624,339.4473` with `BLIP_RC_GUNSLINGER_2`; record 87 /
  `RGUN3` / Billy Midnight at `1231.35,-1299.684,75.9034` with
  `BLIP_RC_GUNSLINGER_3`; and record 88 / `RGUN5` / Black Belle at
  `2492.992,-420.529,43.78334` with `BLIP_RC_GUNSLINGER_5`.
- The generic stranger scripts store Rockstar's live blip in
  `Global_1347702[record].f_37` and use the same `-1337945352` coordinate-blip
  style used by the existing map module.

`collectibles_map.cpp` now polls the feature from the module's existing
two-second map update. The start gate is completed `RCAL11`, with possession of
all four photographs as a hand-off/save fallback. A custom marker is retired
when its branch mission completes, while that branch script is running, or
whenever Rockstar's own f_37 blip exists, preventing completed markers, stale
handles, and custom/vanilla duplicates (including a script-local objective
marker used after the world blip is retired).

Issue-local static checks confirmed all four records have unique story indices,
mission IDs, photographs, coordinates, icons and names; the implementation only
reads the vanilla registry; and the periodic call occurs before the native
carving early return. Per swarm policy, no compile, install, commit, push, or
GitHub label/state change was performed here.

## Runtime acceptance

1. Load a save before meeting Levin and Calloway: none of the four gunslinger
   markers should be added by the mod.
2. Finish the Valentine saloon introduction without inspecting any photograph:
   all four named gunslinger icons should appear on the map at once.
3. Inspect one photograph: its Rockstar marker should replace, not overlap, the
   mod marker; the other three remain visible.
4. Complete one gunslinger branch: that marker should disappear and remain gone
   after saving/reloading, while unfinished branches remain visible.

## Integration

GameplayTweaks built and installed with matching ASI SHA-256
`7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`.
