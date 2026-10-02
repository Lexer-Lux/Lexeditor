# Effects, Misc. and Encumbrance

## Editor access

**Effects** exposes documented properties on every existing special-effect
record. All effects includes unlinked/custom records; Equipment, Spells and
Items filter actual references in the selected archive. Unknown, legacy and
padding fields remain protected.

For Grass Crest Shield, use **Effects > Equipment > Grass Crest Shield (6890) >
Recovery adjustment (stamina/second)** or follow the item's **Linked effects**
button. Modified item references are followed rather than inferred from names.
A shared effect changes every item or ability that uses it.

**Misc.** contains base regeneration, in stamina per second. **Encumbrance**
contains five movement classes, their load ranges and recovery percentages.
Light, Medium and Heavy have editable upper limits; the adjacent lower limits
are derived. Ultralight shares Light's limit and requires the game's special
movement condition. The list displays the native class IDs, 0 through 4.

## Independent tweaks and preservation

Enable **Stamina rebalance** in **Tweaks** to apply the configured Misc. baseline
and the shield bonus. Its proposed settings are 60 base and +5 shield, and it
starts disabled. Enable **Encumbrance rules** independently to use the class
settings. Original limits are 25%/50%/100%, with recovery multipliers of
100%/100%/100%/80%/70%. No preset is applied by opening the editor.

Save writes the isolated project. Apply, with the game closed, installs the saved
archive and enabled native settings. The shield override is projected at Apply
time, never written over the project's authored effect value. Disabling a tweak
and applying restores its native defaults and removes its override, leaving the
other toggle intact. Restore original restores owned installed files without
changing project settings.

Existing shield variants are resolved through their actual passive references.
Missing or ambiguous custom references are refused. Other items sharing the
resolved effect change too. The existing single-project archive deployment is
retained; this PR does not claim multi-mod merging.

## Sources

The full effect definitions, annotations, names and enums are selectively
vendored from Smithbox revision
`cbd477a8fd6d436b3e011c8548e1de8fd8876918` under MIT. Exact source paths, Git
hashes, transformations and independent semantic digests are recorded in
`metadata/EFFECT_SOURCE.json`. Other existing metadata retains `SOURCE.json`.
The original notices remain in `credits.md`.

The initial recovery-cell investigation also consulted Smithbox revision
`057b417887cc7d0ddc8001602be3f5339f42c74f`,
`Smithbox.Release/Output/Assets/PARAM/DS1R/Defs/SpEffect.xml`, blob
`30411975bed40f56ea53247a93807c9cc099cfe1`, and Paramdex
`DS1R/Names/SpEffectParam.txt`, blob
`77e53462c28ea28e1abb140eea29d177da8bff74`.

Independent offset cross-check:
[Dark-Souls-1-Overhaul](https://github.com/metal-crow/Dark-Souls-1-Overhaul),
revision `2a3d8cbe2acee663bef03c7be4f968dbb68f951f`,
`SpEffectEditor-Remaster.CT`, a four-byte recovery modifier at `+B8`.
No Cheat Engine or upstream executable code is copied.

## Native evidence and limits

`codex/ds1/stamina-recovery.md` records the privately inspected executable's
fingerprint, baseline getter, class selector, class recovery factors and
within-class fraction. It also credits Microsoft's PE and x64 unwind references.
`encumbrance.S` is original replacement assembly, not a game disassembly dump.

Tests execute selected functions from the identified private image in an isolated
harness. The executable is not redistributed. Synthetic Apply/Restore and native
function tests do not establish Windows game startup, real animation behavior,
every effect's activation/stacking, or multiplayer safety. Initial candidates
must be tested offline.

Animation timing, invincibility windows and other load-dependent formulas are
not represented by invented editable fields. Player resonance effects 40-44
remain effects, not substitutes for the engine baseline. Other independently
owned executable patches, including the separate equip-load display PR, are
refused rather than overwritten. Keep #758 open until installed-game acceptance.
