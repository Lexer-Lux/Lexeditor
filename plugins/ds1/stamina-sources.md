# Effects, Misc. and Encumbrance

## Editor access

**Effects** exposes documented properties on every existing special-effect
record. All effects includes unlinked/custom records. Equipment, Spells and
Items filter actual references in the selected archive. Unknown, legacy and
padding fields remain protected.

For Grass Crest Shield, use **Effects > Equipment > Grass Crest Shield (6890) >
Recovery adjustment (stamina/second)** or follow the item's **Linked effects**
button. Modified references are followed, not inferred from names. A shared
effect changes every item or ability using that record.

**Misc.** edits base regeneration, in stamina per second. **Encumbrance > Bands**
edits numeric load ranges, existing movement profiles and independent recovery
percentages. Add splits a range; Delete merges with a neighbour whose retained
properties you explicitly choose. Special-light and forced-overburdened
conditions belong to **Overrides**. See `load-bands.md` for boundaries,
persistence, migration and native compatibility.

## Apply and restore

New native projects start with vanilla values. Save writes the isolated
project. Information > Apply combines saved native rules and enabled library
tweak mods through the same composer, then installs the project's parameter
archive. The library's schema-driven Tweaks interface is retained. No baked-in
60/+5 preset or hidden shield overlay runs inside the editor.

Restore original restores verified owned output without changing project
values or library switches. Conflicts and foreign installed changes are
refused. The executable and parameter archive are separate filesystem writes,
with explicit interruption recovery and guarded native rollback. This does
not provide multi-mod parameter-archive merging.

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

`codex/ds1/stamina-recovery.md` records the privately inspected baseline getter,
movement selector, recovery factors and within-class interpolation.
`load-bands.md` describes how the current project editor exports these rules
to the shared composer. Previous standalone encoders exist only for draft
identification/restoration; they are not the current Apply path.

Generated fixtures test documented fields, byte/bit preservation, exact
no-op/reversion, linked references, invalid inputs, save/discard and protected
writes. Separate semantic digests check consumed metadata against the pinned
upstream snapshot. Private-image tests are optional and never bundle game
bytes. Current-head results belong in the PR and its CI evidence, not inferred
from a previous draft's successful tests.

Rendered controls and isolated function execution do not establish game
startup, animation timing, every effect's activation/stacking or online safety.
Initial gameplay testing must be offline.
