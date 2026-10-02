# Effects editor and stamina recovery scope

Related work: #758. Dark Souls Remastered only; Prepare to Die Edition is not supported.

## Editor access

Select a mod project, open **Effects > Equipment**, and select **Grass Crest Shield (6890)**. The **Recovery adjustment (stamina/second)** property is a signed additive modifier, not a percentage or the player's final recovery rate. The editor reads the selected archive; opening it applies no balance preset.

An item's **Linked effects** section follows the item's current references. Use that link for a modified shield instead of assuming it still uses 6890. Every item or ability that shares an effect uses the same edited record. The usage help counts direct references in supported parameter tables, not every possible script or animation call.

The tab now edits all documented properties on existing special-effect records: duration, trigger intervals, HP and stamina changes, damage and defence modifiers, status buildup and resistances, targeting flags, immunities, stacking rules, and linked effects. Known options use named selectors, flags use checkboxes, and numbers use the published bounds. Existing unidentified values remain intact. Padding, legacy fields and insufficiently documented properties are protected.

**All effects** includes unlinked records. **Equipment**, **Spells**, and **Items** filter actual references in the current archive, not guesses from reference names. Custom IDs without a reference label use their stored row name or an ID fallback.

Save writes the isolated mod project. Apply and Restore original retain the existing explicit deployment behavior. Vanilla stays read-only. The shared Data Map distinguishes structured effect editing from unmapped data and native game rules.

## Binary layout and provenance

`SpEffectParam.param` contains `SP_EFFECT_PARAM_ST` records with 368-byte rows and header version 1. The recovery modifier is a signed 32-bit field at byte 184 (`0xB8`). This change reuses the existing BND3/DCX/PARAM reader, field codecs, in-place edits, and project lifecycle. It does not add another archive codec or executable hook.

The full effect metadata is selectively vendored from **Vawser and Smithbox contributors**, revision `cbd477a8fd6d436b3e011c8548e1de8fd8876918`, under MIT. Exact upstream paths, original hashes, transformation notes, and semantic integrity hashes are in `metadata/EFFECT_SOURCE.json`. The existing MIT notice is retained in `credits.md`. The other parameter metadata retains the pins in `metadata/SOURCE.json`. No Smithbox executable, dependencies, fonts, or proprietary game data are included.

Earlier recovery-field research used Smithbox revision `057b417887cc7d0ddc8001602be3f5339f42c74f`, `Smithbox.Release/Output/Assets/PARAM/DS1R/Defs/SpEffect.xml`, blob `30411975bed40f56ea53247a93807c9cc099cfe1`. Paramdex's `DS1R/Names/SpEffectParam.txt`, blob `77e53462c28ea28e1abb140eea29d177da8bff74`, supplied reference identities. Metal-Crow and Dark-Souls-1-Overhaul contributors' `SpEffectEditor-Remaster.CT`, revision `2a3d8cbe2acee663bef03c7be4f968dbb68f951f`, independently corroborated the four-byte `+B8` recovery field. These sources are credited in `credits.md`; no Cheat Engine or injection code is copied.

## What remains separate

This editor does **not** expose a verified native absolute base-regeneration constant or an equip-load threshold/formula. Armour penalty reference groups 6200-6233 are not presented as percentage encumbrance tiers. Reference rows 40-44 describe player resonance effects; their names alone do not prove activation and stacking behavior or make them a verified global baseline control.

Finishing that part of #758 still requires tracing the identified Remastered build's actual recovery calculation and modifiers, then implementing the proved data setting or version-guarded Hext patch through the existing tweak mechanism. No guessed offsets, hardcoded baseline of 45, or substitute resonance-row baseline are included.

This PR is effect-record editing, not the complete independently toggleable stamina rebalance. It must not close #758 on that basis.

## Verification boundary

Generated fixtures test every editable effect property, changes restricted to its intended bytes or bits, exact no-op/reversion, linked references, unknown values, invalid input/layout rejection, save/reopen/discard, Vanilla protection, and synthetic Apply/Restore. A separate metadata test compares the consumed definitions, names and options with digests computed from the pinned upstream snapshot.

The headless browser check exercises the actual shared editor controls, small-window paging/scrolling, named effect links beyond the first list page, the Data Map, save/reopen/discard, and read-only Vanilla. Synthetic archives and rendered controls do not demonstrate retail in-game timing, effect activation, stacking, or native baseline compatibility. Those remain separate installed-game acceptance checks.
