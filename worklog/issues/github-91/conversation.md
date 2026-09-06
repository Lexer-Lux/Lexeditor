# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5349357854 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/91

Created: 2026-09-04T14:33:25Z; updated: 2026-09-05T06:05:06Z

Exact metadata: [source record](sources/issue-5349357854-3f258b12021b10f3adf377100dbca2f3fa85fc5d61d4a796067b314c9094a9d5.json).

Add a Cards tab that can create, delete, and edit Triple Triad cards. The editor must preserve valid card data and expose the card properties through the normal Lexeditor editing, reference, save, and mod-composition systems.

## issue 5349357854 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/91

Created: 2026-09-04T14:33:25Z; updated: 2026-09-06T12:46:05Z

Exact metadata: [source record](sources/issue-5349357854-53df56c07d2859002e0c66b60e2bfe631579fbc467b4015df9d4b5486ffcebc5.json).

Existing Triple Triad cards now support names, ranks, elements and selection power.

**Incomplete:** creating/deleting card types still needs engine, artwork, deck, reward and save support; existing-card edits also need in-game validation. The current fixed-slot editor does not fulfil the whole request. The artwork/NPC-deck redesign remains #300.

## issue 5349357854 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/91

Created: 2026-09-04T14:33:25Z; updated: 2026-09-06T12:46:05Z

Exact metadata: [source record](sources/issue-5349357854-fea455819da16b7e8661bf18fc72aad720a407f3af81b992857140d9dca10e7b.json).

Existing Triple Triad cards now support names, ranks, elements and selection power.

**Incomplete:** creating/deleting card types still needs engine, artwork, deck, reward and save support; existing-card edits also need in-game validation. The current fixed-slot editor does not fulfil the whole request. The artwork/NPC-deck redesign remains #300.

## comment 5549858497 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/91#issuecomment-5549858497

Created: 2026-09-05T06:05:06Z; updated: 2026-09-05T06:05:06Z

Exact metadata: [source record](sources/comment-5549858497-7416623031d7f111bd238be694c224fecc1f2b41fecbdaa8cc87bb722596f15f.json).

Existing cards now have editable names, four ranks, element and selection power in the Cards tab. Save writes the name override and updates both card-property tables. Temporary editor tests confirmed saving and reloading both values; in-game appearance and play still need confirmation.

Adding card types is a separate engine and save change. FFNx rejects card-name IDs above 109, and the PC save layout fixes common counts and rare-card locations in separate arrays. Extra cards also need support in artwork, decks, rewards, Card Mod and selection. Adding one card requires most of the same infrastructure as adding several. The useful first test is one extra card that can be acquired, played, won or lost, refined, and retained after save/load without affecting an existing save. Creation and deletion remain unfinished, so this issue stays actionable.

