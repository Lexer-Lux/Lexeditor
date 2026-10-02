# Stamina recovery editor: scope and sources

Related work: #758. Dark Souls Remastered only. Prepare to Die Edition is not supported by this change.

## Editor access

Select a mod project. Open **Stamina > Equipment effects**, select **Grass Crest Shield (6890)**, and edit **Recovery adjustment (stamina/second)**. This is a signed additive recovery-speed modifier, not a percentage or the player's final recovery rate. Values are read from the selected archive; opening the editor applies no balance preset.

The item's detail panel also has a **Linked recovery effects** section. Use that link for a modified shield: it follows the item's current passive-effect reference instead of assuming it still points to 6890. Effects can be shared by multiple items, including upgrade variants. The effect detail shows the number of direct equipment references and gives examples in its help. It does not claim to trace every script or other effect source.

**Armour penalties** exposes the known per-piece penalty records. These are not equip-load percentage tiers. **Player effects** exposes the named resonance-effect records as raw modifiers, with an explicit warning that they are not a verified global baseline setting. **All effects** permits editing the same reviewed cell on other existing effect records. No effect rows or gameplay activation hooks are created.

Save writes the existing isolated mod archive. Apply and Restore original retain the plugin's existing explicit deployment behavior. Vanilla remains read-only. This is editor access, not yet the complete independently toggleable rebalance requested by #758.

## Data map

| Data | Coverage |
| --- | --- |
| `GameParam.parambnd.dcx / SpEffectParam.param` | Validated optional table; existing BND3/DCX and PARAM codecs reused |
| `SP_EFFECT_PARAM_ST` recovery cell | Structured editable signed 32-bit cell at `0xB8`; all other row bytes preserved |
| Weapon passive effects | Read actual `residentSpEffectId`, `residentSpEffectId1`, `residentSpEffectId2` references |
| Armour passive effects | Read actual `residentSpEffectId`, `residentSpEffectId2`, `residentSpEffectId3` references |
| Ring passive effects | `refId` interpreted as an effect only when `refCategory == 2` |
| Direct equipment ownership | Resolved from the current archive, refreshed after reference/category edits |
| Effect activation/stacking from scripts, events and animations | Not fully traced; never inferred from a reference name |
| Native absolute base recovery, equip-load thresholds/formula | Not mapped or editable by this change |
| Executable patch, global baseline hook, full rebalance toggle | Not implemented |

## Reviewed binary layout

Primary reference: [Smithbox](https://github.com/vawser/Smithbox) revision `057b417887cc7d0ddc8001602be3f5339f42c74f`, path `Smithbox.Release/Output/Assets/PARAM/DS1R/Defs/SpEffect.xml`, Git blob `30411975bed40f56ea53247a93807c9cc099cfe1`.

The definition describes `SP_EFFECT_PARAM_ST`, little endian, `Unk06` 1, definition version 104. Its field layout totals 368 bytes. The first 46 fields are four bytes each, placing signed `staminaRecoverChangeSpeed` at byte 184 (`0xB8`). The declared editing range is -100 to 100. The Japanese description says the modifier adds to/subtracts from the reference and initial recovery speeds in the recovery calculation. It is distinct from `changeStaminaPoint`, a stamina-change/damage field.

The implementation accepts header version 1 and a 368-byte row stride, matching that published layout. This is source-derived compatibility, not a claim that this session measured a retail executable/archive. Wrong type, version, boundaries, duplicate IDs and overlapping rows fail closed. Missing effect tables retain existing item editing but produce an actionable error when stamina editing is requested.

Independent cross-check: [Dark-Souls-1-Overhaul](https://github.com/metal-crow/Dark-Souls-1-Overhaul), revision `2a3d8cbe2acee663bef03c7be4f968dbb68f951f`, `SpEffectEditor-Remaster.CT`, documents a four-byte `staminaRecoverChangeSpeed` cell at `+B8`. No Cheat Engine code, injection code or upstream executable code is copied.

Reference identities: [Paramdex](https://github.com/soulsmods/Paramdex), `DS1R/Names/SpEffectParam.txt`, Git blob `77e53462c28ea28e1abb140eea29d177da8bff74`. Useful entries include 6890 Grass Crest Shield, 6920 Mask of the Child, 2013 Cloranthy Ring, and armour penalty groups 6200-6203, 6210-6213, 6220-6223 and 6230-6233. Labels are reference metadata, not activation evidence.

The existing pinned Smithbox weapon, protector and accessory metadata identifies the passive reference fields and the accessory reference-category discriminator. No proprietary game data is redistributed. Test values, equipment IDs and archive payloads are generated fixtures, not extracted vanilla balance data.

## Baseline investigation and required verification

Reviewed the published DS1R `SpEffect`, `MoveParam`, `CalcCorrectGraph` definitions/names, existing editor metadata and public Remastered effect-editor references. `MoveParam` exposes animation IDs; the reviewed graph names did not establish a base-recovery curve. This does not prove the game has no baseline constant or load-dependent formula.

Row-name metadata describes effect 40 as the no-resonance player effect, alongside levels 41-44. That alone does not prove which states activate them, whether they stack, or whether changing one produces a global baseline adjustment. Do not treat row 40 as a proved replacement for an absolute base-regeneration control.

To finish that part of #758, inspect an identified Remastered executable/build and its actual parameter archive, trace the recovery calculation and state/load modifiers, then implement a verified data setting or version-guarded patch through the repository's existing tweak/deployment system. No guessed offsets or hardcoded baseline of 45 are included here.

Parser/service and browser tests use synthetic archives. Retail acceptance must separately check recovery with/without the shield, relevant upgrades, armour pieces, load conditions, other recovery effects, save/reload and restoration. Synthetic preservation tests do not demonstrate in-game timing or executable compatibility.
