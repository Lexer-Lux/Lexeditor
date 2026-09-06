# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356398026 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/300

Created: 2026-09-05T07:18:40Z; updated: 2026-09-05T07:18:40Z

Exact metadata: [source record](sources/issue-5356398026-59536e1802fd259fff8805c677cc266fb6871b5af7ea6425b65c74c19a4c4499.json).

Rework the Cards tab with two subtabs:

- Cards: show the actual Triple Triad card artwork, with editable ranks on its top, right, bottom, and left. Allow editing the element and show its icon.
- Players: inspect and edit the cards played by NPCs.

Use CCGroup's card-values and NPC-card-players layout as the reference. This is a deferred redesign; the existing fixed-slot editing work is tracked in #91. Expanding the game's card-slot limit is a separate decision.


## issue 5356398026 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/300

Created: 2026-09-05T07:18:40Z; updated: 2026-09-06T12:59:16Z

Exact metadata: [source record](sources/issue-5356398026-b31a5c10888141d864dbc37a6d45bb5bd487f4b1b577915e3ee33407b95bd0e8.json).

Show card artwork with editable directional ranks and element icons, plus a Players subtab for NPC decks. Use the requested CCGroup-style layout.

**Status: Deferred redesign, not a test-ready feature.** The desired layout is already specified; development and verified deck editing remain. Extra card slots are separate from this redesign and remain part of #91.
