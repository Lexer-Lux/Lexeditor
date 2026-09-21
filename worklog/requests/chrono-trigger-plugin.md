# Chrono Trigger Plugin — fresh replacement handoff

- Branch: `codex/chrono-trigger-plugin`; PR title: `Chrono Trigger Plugin`; never merge from agent work.
- Scope: Steam only. #454 is rejected historical evidence, not architecture.
- Current vertical slice: ARC1 read -> keyed localization / fixed-size Mapinfo / palettes / exits / treasure / seven active fixed Steam world headers -> external project -> deterministic CTP -> reopen.
- Evidence: synthetic roundtrip coverage verifies byte-preserving edits and immutable installed `resources.bin`; rendered Playwright acceptance now exercises text plus every format-specific screen, including a world-header save. CI artifacts still require inspection before visual acceptance is claimed.
- Licensing: CTViewer + ct_nx are MIT references. ChronoMod/CTExt lack a clear top-level repository license in the audited revisions, so no code/binary is copied or bundled. Temporal Redux/CTNx are GPL evidence-only.
- Data Map: Mapinfo, palettes and fixed 23-byte world headers are integrated. Atel, map painting/tiles, BGAnime, world map/exit/script bodies, character assets and gameplay tables remain visibly not integrated.
- CI note: repository-wide shared/plugin verification currently also reports an FF7R project-descriptor failure outside this branch's game scope; do not repair FF7R from the Chrono PR.
- Next agent work: finish current CI/browser artifacts and screenshot inspection, then only add further Steam families when current-PC format evidence supports a useful safe editor. Real-game CTP loading remains a separate acceptance requirement.
