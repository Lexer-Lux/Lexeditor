# DS1 spell stamina data paths

Verified against the fingerprinted Remastered `GameParam.parambnd.dcx`
(141 Magic rows) with the repo's own parsers. Foundation for #746.

## Magic.stamina: the per-spell stamina cost

- `Magic.stamina` (s16 at row offset 14, 0-9999) is 0 on all 141 vanilla
  rows. Spells cost no stamina unmodded.
- The engine subtracts it from the caster's stamina when the spell is used
  (Souls Modding, param:magic, Dark Souls 1 section), so writing it is a
  complete stamina-cost tweak with no native patch; disabling the mod
  restores vanilla's zeros exactly.
- Contract: the Spell Stamina Costs tweak sets each spell's Elden Ring
  stamina cost (its `tools/spell_stamina_costs.json`, copied from Elden
  Ring's published per-spell values). Elden Ring's pool matches DS1's
  scale, so the values transfer verbatim, and every cost edits in the
  Spells list and in Stats > Spell requirements.

## NPC mirrors and the uncastable rows

- An NPC spell (id + 10000) costs what the player's copy costs. Row 14300
  is Iron Flesh's NPC copy (same bullet reference) despite its reference
  name.
- Rows 5710 and 15710, the Karmic Justice explosion pseudo-rows (no slot,
  no uses), stay 0.
