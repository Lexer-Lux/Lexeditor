# World-map scripts, and the vehicle warps

The editability audit listed "world-map vehicle records" as a table no page
reads. That is wrong in one way and right in another, and this page records
both, because the difference decides what can be built.

- Rinoa's Toolset's "World Map vehicles" feature is a **3D viewer** of the
  vehicle models, not an editor of a placement table (its own README lists it
  under "Features - 3D", beside battle stages and train-track visualisation).
  World-map models are outside this plugin's scope, which
  [asset-tabs.md](asset-tabs.md) already states.
- What the world map does store for vehicles is a **script section**: `wmsetus.obj`
  section 11, "Vehicle warp scripts" in the FF8 modding wiki's world-map
  reference. The wiki's section list also names section 7 player-location
  scripts, 9 entity-spawn scripts, 10 entity-spawn positions, 12 train exit
  positions, 13 side-quest dialog texts and 36 event scripts.

## The container, and what was confirmed in the installed file

The wiki's Appendix A gives the generic script container: one 32-bit offset per
script, terminated by a zero sentinel, then the bytecode. A script ends at its
own `RETURN` (`0xFF16`), not at the next table offset — which the wiki notes
matters in section 36, where two scripts sit earlier in the file than the entry
listed before them.

Measured on the installed `wmsetus.obj`:

| Fact | Value |
| --- | --- |
| Section 11 size | 172 bytes |
| Offset table | 20, 56, 92, 128, then the zero sentinel at 16 |
| Bodies | 34, 34, 34 and 38 bytes, each ending at `RETURN` |
| First words | `0xFF01 0x0000 0xFF06 <operand>`, with operands 205, 300, 329 and 406 |

Four scripts, each the same shape and a different value: that is what a
"warp somewhere" script looks like, and it matches the wiki's description that
these scripts hand a destination back through a return value.

## What the plugin does now

`plugins/ff8/world_map.py` reads those scripts (`scripts_in_section`,
`vehicle_warp_scripts`) and `tests/ff8/verify_ff8_world_scripts.py` proves the
table shape, the sentinel, that each body ends at `RETURN`, and that the four
scripts carry four different values. No page shows them yet; the World tab was
being edited by another lane while this landed.

## What is not established

- **Which opcode does what.** The wiki names `SET_RETURN_VALUE` as `0xFF15`
  while the observed first word is `0xFF01` and the operand follows `0xFF06`.
  The word names are not proved here, so the scripts are shown as byte ranges,
  not as decoded statements.
- **Section 9's extent rule.** The wiki calls section 9 the exception — spawn
  lists that end on `END` (`0xFF05`) and run to the next offset — but its table
  does not parse cleanly with section 11's rule, so nothing is claimed for it.
  Sections 7, 9, 10, 12, 13 and 36 remain unread.
