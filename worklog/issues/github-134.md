# #134: Configurable horse feeding and bond amounts

[Live issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/134)

## Scope

Allow chosen feed items with configured bond amounts, integrated with actual feeding. Do not restore the rejected after-consumption watcher. No new permission is needed for investigation.

## Source recovery on 2026-09-08

The current 1491.50 player_horse source disproves the old fixed-20 bond attribution. Actual food processing is func_433 → func_739 → func_454 → func_758/func_760 → func_677. Event 13/14/15 awards have base values 15/5/1; sugarcube/peppermint/bulrush/mace use event16 with base5. Eight herbs skip bonding. Eligibility has45 IDs; preferred selection has11 ordinary feeds then26 herbs. Shared bonus, rank, event-cap and motivation gates still apply.

The constant20 is func_962 and reaches separate f_407 state via func_895; func_739 never calls it. The old GitHub comments remain history. Canonical corrected mechanics: codex/rdr2/horse-feeding.md.

The new resolver tools/research_rdr2_horse_feed_dispatch.py verifies the complete award chain and rejects three mutations (fixed-amount substitution, wrong event routing and wrong attribute). Small report: out/rdr2-horse-feed-dispatch.json. Normalized source SHA-256 da1e95f2042abebc77dcdaedf02cf4310d7db82a747d0e57f2f9918e7cbda2dc. Retained source: C:/RDR2Mod/_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/player_horse.ysc.c.

## Exact next implementation surface

Keep hParam1 item identity in func_739 at annotated0x152FC. Replace its two func_454 call sites with an item-aware award variant that keeps func_454's rank/event-cap/motivation checks, substitutes the configured magnitude once, applies the selected bonus policy consistently and retains func_760/func_472 accounting. Eligibility must also extend func_724; preferred interaction selection must extend func_789. Do not hook generic SET_ATTRIBUTE_POINTS or add an after-consumption award, because neither retains this item-specific path.

No installed-bytecode signature or safe script dispatcher hook is validated. The #228 extraction audit already found the nested script archive uses missing encryption key198; a decompiled annotation is not a file offset. Recovering a verified executable script surface remains agent work. No runtime patch, arbitrary item control, game write or double-award watcher was added.
