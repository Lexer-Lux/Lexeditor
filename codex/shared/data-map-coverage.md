# Data Map interface coverage

`LexeditorUI.dataMap` is the shared fitted Table + Detail composition. It uses
`pagedListDetail`, its saved split, row capacity, selection, sorting and bottom
pager. Long scope notes live in the detail pane; list cells remain one line.
Coverage must be explicit: `structured`, `view`, `source`, or `unavailable`.
A legacy `integrated` status or the presence of a reader/writer alone does not
prove an editor. A structured partial row describes exactly which fields are
exposed. `target`/`targets` link to the actual interface; `dataset` disambiguates
multiple FF9 datasets on one tab. Row IDs distinguish FF7 sections in one file.

## Audited plugin boundaries

- Warband: settings values are structured; item/troop/tree browsers are read-only;
  remaining Module System editing is source-only. Missing source is unavailable.
  Mesh/material/texture dependencies are checked per selected preview.
- FF7 and FF7_2013 share an implementation: bounded KERNEL section fields are
  partial structured support, with individual category links. Names/descriptions
  are read-only. Missing FFNx config is unavailable, not partial integration.
- FF8: every supported record/text/map row links to its actual tab. The named
  subset of init.out is partial, not whole-file coverage. World/field links
  choose Maps > World/Field. FFNx config links to Tweaks > FFNx only when present.
- FF9: available Memoria CSV datasets are structured, each linked to its exact
  dataset. Missing CSVs/config and unresolved p0data containers are unavailable.
- RDR: generated research metadata cannot invent an editor or override verified
  coverage. Only present inventory sources and proved ShopInventory resources
  receive their corresponding interface. Non-shop WGD resources are unavailable.
  Missing packed resources/writer permit read-only shop coverage, not saves.
- RDR2: supported record fields retain explicit partial scope. Preserved weapon
  component META layers have no record editor and are unavailable; preserving
  their bytes does not establish UI integration. Projectile mapping is read-only
  while the runtime switch is disabled. Other writer-registry targets remain
  structured within the described field scope.
- Blank: Data Map explicitly describes an in-memory UI demonstration, not a
  game-file editor.

Tests use synthetic data and actual plugin HTML/CSS/map adapters. They establish
UI behavior and claims for implemented interfaces, not actual game deployment.
