# Chrono Trigger Plugin — fresh replacement handoff

- Branch: `codex/chrono-trigger-plugin`; PR title: `Chrono Trigger Plugin`; never merge from agent work.
- Scope: Steam only. #454 is rejected historical evidence, not architecture.
- First vertical slice: ARC1 read -> keyed localization / fixed-size exits / fixed-size treasure -> external project -> deterministic CTP -> reopen.
- Evidence: core synthetic roundtrip tests pass locally; rendered Playwright check is prepared for repository CI and must be inspected from artifacts before visual acceptance is claimed.
- Licensing: CTViewer + ct_nx are MIT references. ChronoMod/CTExt lack a clear top-level repository license in the audited revisions, so no code/binary is copied or bundled. Temporal Redux/CTNx are GPL evidence-only.
- Data Map: recognized legacy families stay visible. Mapinfo, Atel, maps/tiles, BGAnime, palettes, world data, character assets and gameplay tables remain not integrated until a useful safe editor is implemented.
- Next agent work: land the fresh checkpoint, open the draft PR, run scoped checks/browser artifacts, fix UI defects, then implement additional low-cost proven Steam families (palette and Mapinfo are likely candidates) without hiding remaining gaps.
