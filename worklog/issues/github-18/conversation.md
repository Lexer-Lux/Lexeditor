# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5264309582 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/18

Created: 2026-08-27T05:45:26Z; updated: 2026-09-05T06:00:42Z

Exact metadata: [source record](sources/issue-5264309582-0eed6e0e59cbf18e61b4db6b82f5eabf274cbb39f821ab6b8ff8384b4f173961.json).

The Mobs / Mobs view lists many models with no observed values or archetype, and lets the user save archetype assignments to a CSV that GameplayTweaks does not consume. The UI must not present a dead override as an effective edit.

Make real combatbehaviour.meta and pedhealth.meta archetype editing the primary Mobs view. Model observations may remain read-only only when MobProbe has real values. Do not infer a definitive archetype from an ambiguous health match, and do not offer a save control that changes nothing in game.

## issue 5264309582 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/18

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T12:45:09Z

Exact metadata: [source record](sources/issue-5264309582-2a6ac96610bab650ecc5243f310b7bce036f857355632822f99c0f7f0552baad.json).

Mobs now opens real Combat Profiles and Health archetypes. Unused model-assignment controls were removed; Observed Models is read-only. Typed controls need your check.

- [ ] Restart Lexeditor. Open RDR2 Mobs → Archetypes → Combat Profiles and Health; confirm real values and appropriate number, checkbox and choice controls appear.
- [ ] In a test mod, change one value, save and reopen it. Confirm the edit survives and no model-assignment control claims to affect the game; report the field that fails.

## issue 5264309582 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/18

Created: 2026-08-27T05:45:26Z; updated: 2026-09-06T12:45:09Z

Exact metadata: [source record](sources/issue-5264309582-775b8da60a9e84057e5908c8bfe39ac2c2667bd570c84bb699b4a5d5a43eb678.json).

Mobs now opens real Combat Profiles and Health archetypes. Unused model-assignment controls were removed; Observed Models is read-only. Typed controls need your check.

- [ ] Restart Lexeditor. Open RDR2 Mobs → Archetypes → Combat Profiles and Health; confirm real values and appropriate number, checkbox and choice controls appear.
- [ ] In a test mod, change one value, save and reopen it. Confirm the edit survives and no model-assignment control claims to affect the game; report the field that fails.

## comment 5435213524 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/18#issuecomment-5435213524

Created: 2026-08-27T06:27:06Z; updated: 2026-08-27T06:27:06Z

Exact metadata: [source record](sources/comment-5435213524-08345f8e97b0b50d34eff2087b4f10733f11b5a956a4301d353cacc26d3be73d.json).

Removed the empty no-op model assignment editor. Mobs now opens on Archetypes, where the populated controls edit the real combatbehaviour.meta and pedhealth.meta records. The former Models view is now read-only Observed Models and shows only actual MobProbe evidence. The unused assignment selector, save route, and override file path are gone.

## comment 5549836198 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/18#issuecomment-5549836198

Created: 2026-09-05T06:00:41Z; updated: 2026-09-05T06:00:41Z

Exact metadata: [source record](sources/comment-5549836198-bc2f64aa2385e2ae188beaf142c2c6bb1125893e1cc925c7a265171d529b2944.json).

Combat Profiles now uses number fields, checkboxes, and dropdowns based on the loaded source values. The save handler also rejects invalid numbers, Boolean values, and unknown choices. Hidden checks confirmed the typed controls. Restart Lexeditor and inspect Mobs → Archetypes → Combat Profiles.
