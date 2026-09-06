# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5347715431 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/88

Created: 2026-09-04T11:50:25Z; updated: 2026-09-04T12:25:18Z

Exact metadata: [source record](sources/issue-5347715431-52810fc1b715b04c4e8b95ead9e73ad45c8261b12c7c842afaa4170bdf9aa4e2.json).

Explore and design an optional FF8 De-linearization tweak that makes the game more open.

The tweak can change story gates, world and field access, event order, party availability, and when side content becomes available. It can require both runtime logic and edited game data.

Requirements before implementation:

- Inventory the vanilla gates that force the main-story order.
- Separate hard technical dependencies from narrative ordering.
- Identify field-script, world-map, battle, party, disc, and savemap assumptions that fail when content is reordered.
- Define safe invariants so required characters, vehicles, items, locations, and later events exist before dependent content runs.
- Decide which sequences can move independently and which must remain ordered.
- Specify compatibility with saves, missable content, achievements, and other Tweaks.
- Integrate with Journal #87 through overrideable quest stages and unlock conditions instead of a fixed vanilla sequence.
- Prefer data-driven ordering and conditions over scattered binary patches.
- Do not implement until Lexer approves a concrete progression design.

This issue is waiting for design triage.

## issue 5347715431 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/88

Created: 2026-09-04T11:50:25Z; updated: 2026-09-06T12:45:59Z

Exact metadata: [source record](sources/issue-5347715431-024b1eeeae620ddabca6d0b2e259726ca43d874d481c66522361abd17efd29db.json).

Make FF8 less linear without breaking required characters, vehicles or story events. No concrete progression design has been selected.

- [ ] Choose the initial scope: earlier free travel, selected missions in a different order, or a substantially open world.
- [ ] Describe which locations, vehicles and party members should become available earlier, and which story gates must remain. This is a design decision, not a game test.

## issue 5347715431 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/88

Created: 2026-09-04T11:50:25Z; updated: 2026-09-06T12:45:59Z

Exact metadata: [source record](sources/issue-5347715431-987556ea1c158001a219683d30e328094757907437bbb8a8f5d9d903d472a996.json).

Make FF8 less linear without breaking required characters, vehicles or story events. No concrete progression design has been selected.

- [ ] Choose the initial scope: earlier free travel, selected missions in a different order, or a substantially open world.
- [ ] Describe which locations, vehicles and party members should become available earlier, and which story gates must remain. This is a design decision, not a game test.
