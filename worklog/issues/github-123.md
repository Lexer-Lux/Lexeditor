# #123: Add independent golden overfill to cores and bars

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/123)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #23 worklog](github-123/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-23.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

2026-09-08 local recovery: retained conversation contains the specific bottom-to-top core glyph requirement and transparent-mask method. Recovered hd_0.rpf -> hd/textures/ui/ui_hud.rpf -> rpg_core_health.ytd using RpfCli. Private output: out/rdr2-core-art/. Existing games/rdr2/inventory_icons.py normalizes decoded RSC8 for texfury. Decoded and inspected core_state_0, 7 and 15: 128x128, with opaque grey unfilled glyph and white fill. Raw partial-state tint would obscure the base; masks must separate the fill. No renderer or game art was changed. Other four dictionary names confirmed by archive listing. Legacy RageLib GTA parser cannot load this decoded RSC8 representation; use existing texfury path. Remaining work: deterministic transparent mask dictionary, resident dictionary integration, independent core/bar draw paths and rendered acceptance.

Recovery completed for all five core dictionaries: each contains all 16 core_state_N frames. Empty/middle/full PNGs decoded for each family. Current private research output is 1,898,232 bytes including the unused 470 KB legacy exporter. Automatic review blocked deletion of those exporter helper files without further reason; no deletion workaround used. RpfCli removes temporary archive files itself. Nothing from this private game-art output was published or installed.

## Gold glyph implementation preflight
Failure classes: invented art, opaque partial-state tint, two concentric rings, mixed bar/core timers, and source checks that require rejected behavior. Primary evidence is the extracted five stock core dictionaries and the retained bottom-up glyph decision; live issue still requires independent core/bar values. Sanctioned path is the existing resident generic_textures dictionary, preserving every existing texture, with deterministic transparent masks derived from full/empty/staged stock glyphs. Execute pixel/round-trip preservation checks and a production renderer harness. In-game alignment, draw order and all five HUD seats remain the player-visible boundary. Per-frame work is bounded to existing five meters, two ring sprites and two core sprites per active meter; dictionary requests are gated by loaded state. No per-frame disk writes.

## 2026-09-08 installed independent gold glyph candidate
Implemented separate core glyph and outer-ring dispatch. A core-only timer no longer paints the bar. A full white stock glyph masks binary gold; a transparent bottom-up mask carries only remaining core gold. Calibrator previews a half-full glyph at the same seat. No second ring. Deterministic builder preserves all 152 resident texture payloads exactly and appends 85 glyph textures. Build output is470,514 bytes. Empty/mid/full preview inspected for health and horse stamina. Two mask tests and production C++ render harness pass; three regression mutations fail. Existing reference-binary geometry verifier still cannot run without the missing supplied Hardcore Stamina binary; geometry constants were retained.
Installed ASI SHA256:12C8E7078225280EF18E365FFB49EE6FBE92E3CB023B44F335D370308168DA81. Source/game texture SHA256:E1829B2C21DE2BBA6B037B7390E14189E8080684F00E2FFAAEC77BB75EC541E0. Updated MyOverhaul/stream installer source after checking all existing texture payloads against candidate. Settings unchanged; game not launched. Small prior runtime/texture rollback copies are in out/rdr2-previous-runtime.
Acceptance: restart Story Mode; use the existing Rampage boost controls to activate cores and bars separately and together. Check all three player glyphs and both horse glyphs. Gold must remain at the bottom, shrink toward empty, and reveal white above it; rings must follow only bar time. Developer calibrator (tilde Developer Mode then Numpad0; Numpad1 selects,4/6 and8/2 move,7/9 size,5 saves) shows half-fill without consuming tonics. Report overlap, wrong glyph, opaque rectangle, missing texture or timer coupling. In-game scale, draw order and visibility remain unverified.
Source: tools/prepare_rdr2_gold_cores.py and tools/verify_rdr2_gold_core_render.py; private output out/rdr2-gold-core-candidate/. Do not publish raw game-art research output.
