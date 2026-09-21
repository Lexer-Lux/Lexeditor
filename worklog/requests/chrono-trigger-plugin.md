# Chrono Trigger Plugin — fresh replacement handoff

- Branch: `codex/chrono-trigger-plugin`; PR title: `Chrono Trigger Plugin`; never merge from agent work.
- Scope: Steam only. #454 is rejected historical evidence, not architecture.
- Current vertical slice: ARC1 read -> keyed localization / fixed-size Mapinfo / palettes / exits / treasure / seven active fixed Steam world headers -> external project -> deterministic CTP -> reopen.
- Evidence: synthetic roundtrip coverage verifies byte-preserving edits and immutable installed `resources.bin`. Chrono run 35550552987 passes core on Windows and Ubuntu; its rendered Playwright job passes at 1200x800 and 900x620 with no page errors or body overflow. Artifact 10618029656 was visually inspected across Text, Areas, Worlds, Area Exits, Treasure, Palettes and Data Map, including a world-header save.
- Licensing: CTViewer + ct_nx are MIT references. ChronoMod/CTExt lack a clear top-level repository license in the audited revisions, so no code/binary is copied or bundled. Temporal Redux/CTNx are GPL evidence-only.
- Data Map: Mapinfo, palettes and fixed 23-byte world headers are integrated. Atel, map painting/tiles, BGAnime, world map/exit/script bodies, character assets and gameplay tables remain visibly not integrated.
- CI note: repository-wide shared/plugin verification currently also reports an FF7R project-descriptor failure outside this branch's game scope; do not repair FF7R from the Chrono PR.
- Next agent work: real-game CTP loading remains the outstanding acceptance requirement. Add further Steam families only when current-PC format evidence supports a useful safe editor; do not turn recognized-but-unsafe rows green.
