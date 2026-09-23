# Chrono Trigger Plugin — fresh replacement handoff

- Branch: `codex/chrono-trigger-plugin`; PR #503 / title `Chrono Trigger Plugin`; keep open/draft and never merge from agent work.
- Scope: Steam App ID 613830 only. #454 is rejected historical evidence, not architecture. Issues/issue handoffs are read-only for this worker.
- Source boundary: installed `resources.bin` remains immutable. Current structured editors include localization, Mapinfo, scene tiles/properties/render settings, exits, treasure, palettes, field graphics sets/tile assemblies/chip animations, sprite descriptors/assemblies, world headers/maps/properties/music/colors/navigation.
- Protected gaps: Atel and world-script bodies remain variable/unsafe; raster graphics and unverified gameplay tables remain not integrated. Unknown bits/counts/sentinels/RLE boundaries/trailing bytes stay protected.
- Mod compatibility: standard replacement-only CTP export is implemented. Shared Mod Library import now accepts `.ctp`; direct CTP import can become an editable project. `ChronoCtpAdapter` models an already-installed CTExt's `mods/` + `ctext.json mods.load_order` contract, reports whole-resource conflicts, preserves external order entries, uses a Lexeditor-owned namespace, and has stale/recovery guards.
- Runtime boundary: CTExt is evidence-only and not bundled because the audited repository has no clear top-level redistribution license. Adapter `verified=False` and plugin `mods_load=False`; installed-game activation/removal is still unproved.
- Theme/assets: Chrono contributes only color/theme tokens and shared UI; no game artwork, font, audio or CTExt asset is bundled by this plugin.
- GUI: shared shell, Info/Data Map and shared Table+Detail components are used; browser acceptance drives all integrated screens. A 150%-equivalent small-window pass is now part of the Chrono browser workflow.
- Candidate: Chrono workflow now has an exact-head Windows tracked-source candidate gated by Chrono core/integration/browser checks. Its manifest explicitly says CTExt/proprietary game files are absent and in-game acceptance is false.
- Evidence rule: keep source/preservation, rendered, candidate, mod-compatibility and installed-game evidence separate in PR body. Repository-wide failures owned by other plugins are not Chrono evidence.
- Next: inspect exact-head Chrono CI/rendered/candidate artifacts, fix Chrono-owned defects, then update PR evidence. No further format row should become Integrated without a bounded current-PC write path and preservation tests.
