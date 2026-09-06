# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5349358048 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/92

Created: 2026-09-04T14:33:27Z; updated: 2026-09-04T16:24:06Z

Exact metadata: [source record](sources/issue-5349358048-0441f1732463135b3b1ecc594f63d2ae5dce0d8a459ac48e7f9337ad0aa2bcfc.json).

Add a gameplay Tweak that changes +Stat% abilities into flat +Stat abilities. The in-game names must show +Stat, and the equipped ability must add the stated fixed number of stat points instead of applying a percentage. Keep this separate from the general formulae rework unless the implementation requires one shared hook.

## issue 5349358048 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/92

Created: 2026-09-04T14:33:27Z; updated: 2026-09-06T12:46:08Z

Exact metadata: [source record](sources/issue-5349358048-44ab68ea3a151acbb32146dcd550806f6e2cb982f34a685af184bf9dce9eb183.json).

The optional Flat Stat Abilities tweak now changes percentage bonuses to fixed points and updates matching names. Its gameplay effect needs confirmation.

- [ ] Restart Lexeditor, enable the tweak, save and launch FF8. On a character below the stat cap, equip Str+20; confirm STR rises by exactly 20 and the name no longer says percent.
- [ ] Unequip it, then disable the tweak and relaunch. Confirm the fixed bonus disappears and normal percentage behavior returns; report before/after values.

## comment 5543436320 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/92#issuecomment-5543436320

Created: 2026-09-04T16:24:05Z; updated: 2026-09-04T16:24:05Z

Exact metadata: [source record](sources/comment-5543436320-dc4a781f4f526a1fb664b921c5721b8d8e10c54cc28497dd5975c519f6e816c4.json).

The Tweak is implemented and defaults off. When enabled, it changes the equipped +Stat calculation from a percentage to fixed points for HP, Str, Vit, Mag, Spr, Spd, Eva, Hit, and Luck. It also changes the matching ability names and descriptions from percent to points without replacing unrelated custom text. Static, mutation, save, and composition checks pass. Please enable it and confirm one equipped ability in game; for example, Str+20 must add exactly 20 Str.
