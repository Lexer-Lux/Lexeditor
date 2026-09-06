# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356141143 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/96

Created: 2026-09-05T06:26:46Z; updated: 2026-09-05T06:32:36Z

Exact metadata: [source record](sources/issue-5356141143-821c7bc7b5b741f64e84112e5fe7a7bbcde1d54bdd1054bdb45b523a004a159d.json).

Status: Deferred at Lexer's request. This is not a current implementation priority.

Replace Warband's flat upgrade-link list with clickable troop trees grouped by faction and by tree. Trees grow from the bottom upward. Selecting a troop node shows that troop's details in the right panel. Preserve distinct branches and multiple trees within a faction, with clear upgrade connections.

Acceptance when this work is resumed: choose a faction/tree, follow its branches from bottom to top, and click any troop to view its matching right-side detail. Do not start this work as part of the current UI repair.


## issue 5356141143 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/96

Created: 2026-09-05T06:26:46Z; updated: 2026-09-06T13:31:05Z

Exact metadata: [source record](sources/issue-5356141143-8ab368dcd8db0b451af4259b552a7f9bccc595657ef94be6a386324993e1f551.json).

**Actionable — delivery remains.** Faction/tree selectors, bottom-up upgrade graphs and linked troop details are in draft PR #361, not the normal installed editor. Fixture checks pass, but your actual module is unverified.

A ready-to-run test copy still needs preparing. Roots must sit below upgrades, branch links must match the module, and selecting any node must show that troop’s details.
