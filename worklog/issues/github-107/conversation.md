# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356285266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/107

Created: 2026-08-06T01:36:02Z; updated: 2026-09-05T06:55:06Z

Exact metadata: [source record](sources/issue-5356285266-019195a997b4fb05f93312ee82da6e82731e9d48046c2c5b29d178471204b78c.json).

Can we make it so unique
     weapons, instead of being whole new weapons that are just slightyl
     diffferent and unmoddable, the things that make them different are just
     weapon mods, so it's just liek picking up any other customized version of
     that gun, and then you can just freely mix and match those new mods you've
     found at the gunsmith from then on?"
     Overlaps Lexer-Lux/Lexeditor#203 and Lexer-Lux/Lexeditor#138; those stay separate until this one is scoped.

## issue 5356285266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/107

Created: 2026-08-06T01:36:02Z; updated: 2026-09-06T12:46:15Z

Exact metadata: [source record](sources/issue-5356285266-41427263c7fe68ebd6f50dd61228c28d22e37a286e86328e1651124592315769.json).

Make unique-gun features unlockable parts that can be mixed with normal gunsmith customization, rather than permanently separate, unmodifiable weapons.

**Status: Research only.** A Calloway’s Schofield prototype was proposed, but component and engraved-mesh compatibility remain unproven. Prepare a working example before requesting a design or gameplay review.

## issue 5356285266 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/107

Created: 2026-08-06T01:36:02Z; updated: 2026-09-06T13:54:05Z

Exact metadata: [source record](sources/issue-5356285266-b9e2bd2fc4c1900e0416a1fbe883a0c9f542ddcc737ac676aab7604546a16cab.json).

Make unique-gun features unlockable parts that can be mixed with normal gunsmith customization, rather than permanently separate, unmodifiable weapons.

**Status: Research only.** A Calloway’s Schofield prototype was proposed, but component and engraved-mesh compatibility remain unproven. Prepare a working example before requesting a design or gameplay review.

## comment 5550110671 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/107#issuecomment-5550110671

Created: 2026-08-06T03:57:18Z; updated: 2026-08-06T03:57:18Z

Exact metadata: [source record](sources/comment-5550110671-a4b16335f8bad0eb00409f879986bc4ce6fdab6a1bb2ec9a9a0642d6bc2b8f03.json).

Research result: feasible, but it is a catalog/component conversion rather than a stat toggle. Unique guns are standalone `CI_CATEGORY_WEAPON_UNIQUE` identities; ordinary customization uses weapon-specific slots and `CWeaponComponentInfo`, whose records can carry real accuracy, FOV, and damage modifiers. Prototype one revolver: turn its distinctive parts into compatible components, add gunsmith/catalog entries, and make its pickup unlock them. Then verify gunsmith visibility, installation, save persistence, dual wield, mission rewards, and compendium credit. The main unknown is whether each engraved mesh can be reused as a component or needs custom model work. Calloway's Schofield is the recommended first proof.
