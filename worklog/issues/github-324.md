# #324: Add useful, accurate details to Scan

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/324)

## Requirements and decisions

Expanded Scan information must come from real enemy data rather than hand-maintained enemy prose. The requested first details are elemental weaknesses/resistances and Devour results.

Do not label Low/Mid/High Devour tiers with universal numeric cut-offs: vanilla has exceptions. Preserve the enemy's hand-written Scan description unless the editor user explicitly asks to update generated details.

## Current implementation and evidence

The enemy DAT already exposes all eight element-defence bytes and all three Devour IDs. FF8 Ultimate Editor commit `343d97e9` provides the proven Devour mapping (0-15 plus 255 Immune); it is now stored in `games/ff8/schema/devour.json` and exposed as named choices rather than an unexplained raw ID.

`games/ff8/scan_details.py` generates an FF8-encodable `DETAILS` page from the current enemy table: Weak/Resist/Immune/Absorb element groups plus Low/Mid/High Devour outcomes. The Enemies -> Battle Text -> Scan panel previews that page and offers **UPDATE DETAILS** for the selected enemy or **UPDATE ALL** for every available enemy. Updating replaces Lexeditor's previous terminal `DETAILS` page instead of silently overwriting the original description; Save then uses the existing `battle_scans.msd` writer.

`tools/verify_ff8_scan_details_issue_324.py` checks the full Devour mapping, all four element classifications, neutral and unknown preservation, Scan text encoding, and the editor integration markers. The inline editor script also passes `node --check`.

## Player acceptance remaining

In a copied mod, pick an enemy with known elemental modifiers and Devour results. In Battle Text -> Scan, use UPDATE DETAILS and Save. Launch with the existing Enhanced Scan path, Scan that enemy, and confirm the extra DETAILS page appears with the same element and Devour values shown in the editor. Repeat after changing one element defence and one Devour tier, then use UPDATE DETAILS again and verify the page updates instead of duplicating.

Automated data/encoding/editor checks do not claim in-game text-layout acceptance.
