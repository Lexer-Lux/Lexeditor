# #239: Choose the pocketwatch display font

[Full request and discussion archive](github-239/conversation.md)

## Requirements and decisions

Recover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.

## Next agent work

Read the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #147 worklog](github-239/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-147.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-06 — runtime/editor mismatch repaired

The public Lexeditor schema already exposed the requested five choices, but the actual runtime still hard-coded `$title` and the runtime INI/private schema had no `FontFace` setting. Implemented the missing runtime half rather than treating the issue as source-complete.

`Pocketwatch|FontFace` now hot-reloads through the existing two-second settings poll, validates exactly five built-in faces and falls back to `body1` (Classic Serif): `body1`, `FixedWidthNumbers`, `catalog2`, `Font5`, and `title`. The runtime text markup uses the selected face instead of hard-coded RDR Lino. Both runtime INI locations define `FontFace=body1`; the private settings schema now mirrors the public labels: Classic Serif, Watch Numerals, Catalogue Numerals, Redemption, and RDR Lino (Previous).

Product commit `f1389f64e843c8c6cd3d2ca1130cf16effbaa2ac`. The implementation workflow passed settings lifecycle/menu checks and reproducible generation. Permanent verifier `verify_pocketwatch_font_issue_147.py` and CI follow-up `f901a724effe4b298c12fd88a85029e8dfd1a091` assert the five choices, Classic Serif default, dynamic `$%s` markup, fallback and hot-reload contract. Actual native-font appearance still requires a built/installed candidate and visual acceptance.
