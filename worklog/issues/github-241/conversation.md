# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356317206 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/241

Created: 2026-08-10T11:00:52Z; updated: 2026-09-05T07:02:21Z

Exact metadata: [source record](sources/issue-5356317206-df7855ea32b1105b3c620c7528acebcb807e638a4d1420c602ddd37b346599d1.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/1782daea-28c9-4f86-8708-06086065b254" />

this should not be happening.

## issue 5356317206 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/241

Created: 2026-08-10T11:00:52Z; updated: 2026-09-06T13:31:51Z

Exact metadata: [source record](sources/issue-5356317206-7d39537e635cd0e9eca690653a4d7df8b7c1a6b2be4b6e77c0784fe37ce3a3f1.json).

**Closed historical report.** Activation requires a physical camp, with a short streaming grace before deactivation. The last repair note here was source-only; delivery and current campsite behavior remain in #101 and #244.

[Original screenshot](https://github.com/user-attachments/assets/1782daea-28c9-4f86-8708-06086065b254).

## comment 5550147031 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/241#issuecomment-5550147031

Created: 2026-08-10T11:28:14Z; updated: 2026-08-10T11:28:14Z

Exact metadata: [source record](sources/comment-5550147031-6097f5e1964d98bb0283a5b95c83932fbaaaac93555314c2c56e9a2658611c11.json).

Source repair complete. Exact cause: activation trusted proximity plus a generic `player_camp` script reference, not the physical camp at this saved site. The repaired path uses Story's exact `P_CAMPFIRE02X_COMBO` object at the authored origin as the postcondition; the activation prompt stays unavailable without it, stale/generic script refs no longer prove the site materialized, and a nearby activated ghost gets a 15-second streaming grace before it is demoted to inactive and saved. Distant intentionally-unstreamed camps are not demoted and the authored campsite row is never deleted. New Lexer-Lux/Lexeditor#241 and existing Lexer-Lux/Lexeditor#211 verifiers pass. This source change was made after `FC692F30...43589`, so it remains `actionable` and is not part of the currently waiting installer.
