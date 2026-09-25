# World-map scripts, and the vehicle warps

The editability audit listed "world-map vehicle records" as a table no page
reads. That is wrong in one way and right in another, and this page records
both, because the difference decides what can be built.

- Rinoa's Toolset's "World Map vehicles" feature is a **3D viewer** of the
  vehicle models, not an editor of a placement table (its own README lists it
  under "Features - 3D", beside battle stages and train-track visualisation).
  World-map models are outside this plugin's scope, which
  [asset-tabs.md](asset-tabs.md) already states.
- What the world map does store for vehicles is a **script section**: `wmsetus.obj`
  section 11, "Vehicle warp scripts" in the FF8 modding wiki's world-map
  reference. The wiki's section list also names section 7 player-location
  scripts, 9 entity-spawn scripts, 10 entity-spawn positions, 12 train exit
  positions, 13 side-quest dialog texts and 36 event scripts.

## The container, and what was confirmed in the installed file

The wiki's Appendix A gives the generic script container: one 32-bit offset per
script, terminated by a zero sentinel, then the bytecode. A script ends at its
own `RETURN` (`0xFF16`), not at the next table offset — which the wiki notes
matters in section 36, where two scripts sit earlier in the file than the entry
listed before them.

Measured on the installed `wmsetus.obj`:

| Fact | Value |
| --- | --- |
| Section 11 size | 172 bytes |
| Offset table | 20, 56, 92, 128, then the zero sentinel at 16 |
| Bodies | 34, 34, 34 and 38 bytes, each ending at `RETURN` |
| First words | `0xFF01 0x0000 0xFF06 <operand>`, with operands 205, 300, 329 and 406 |

Four scripts, each the same shape and a different value: that is what a
"warp somewhere" script looks like, and it matches the wiki's description that
these scripts hand a destination back through a return value.

## What the plugin does now

`plugins/ff8/world_map.py` reads those scripts (`scripts_in_section`,
`vehicle_warp_scripts`) and `tests/ff8/verify_ff8_world_scripts.py` proves the
table shape, the sentinel, that each body ends at `RETURN`, and that the four
scripts carry four different values. No page shows them yet; the World tab was
being edited by another lane while this landed.

The same reader takes section 7 (player-location scripts, 38 of them) and
section 36 (event scripts, 92). Section 36 is the section the wiki warns about,
and the installed file confirms the warning: entries 46 and 54 sit earlier in
the file than the entry listed before them (4444 to 3772, 4408 to 3848). Reading
each script to its own `RETURN` handles that; reading to the next table offset
would give those two a negative length, which the check demonstrates by
computing both ways.

## What is not established

- **Which opcode does what.** The wiki names `SET_RETURN_VALUE` as `0xFF15`
  while the observed first word is `0xFF01` and the operand follows `0xFF06`.
  The word names are not proved here, so the scripts are shown as byte ranges,
  not as decoded statements.
- **Section 9's extent rule.** Answered since this page was written: section 9
  uses the same container (20 offsets, sentinel at 80) but its lists are action
  lists. Each ends on `END` (`0xFF05`) and the span runs to the next offset,
  with zero padding after the terminator — 2 bytes for most entries, 6 for the
  last. `entity_spawn_scripts` reads them and reports the padding rather than
  hiding it. Every script section this page names is now read.

## The position tables beside the scripts

Sections 8, 10 and 12 hold fixed records from the start of the section, then a
four-byte footer. This is one convention, not three: the field-return reader
already reads section 8 that way (`FIELD_RETURN_RECORD_SIZE`,
`FIELD_RETURN_FOOTER_SIZE` in `plugins/ff8/world_map.py`), and it is what the
shipped sizes say.

| Section | Records | Record | Bytes in the installed file |
| --- | --- | --- | --- |
| 10 entity spawn positions | 64 | x, y, z int32 then yaw and pitch int16 (wiki's `EntityPosition`) | 1028 = 64 × 16 + 4 |
| 12 train exit positions | 3 | x, y int32, z int16, then two unnamed bytes | 40 = 3 × 12 + 4 |

Both footers are zero in the installed file. The wiki describes section 12 as a
four-byte `entries_size` followed by records; the shipped file does not match
that — its first four bytes are a coordinate and the arithmetic only works with
the count at the end — so the reader follows the file and this page says so.

`entity_spawn_positions` and `train_exit_positions` read both tables and
`tests/ff8/verify_ff8_world_positions.py` proves the counts, the record fields,
the footers, that every coordinate lies inside the range the world projection
uses, and that a section whose size is not records plus a footer is refused.

## Section 13: the world map's own dialog

Section 13 holds the world map's dialog strings: offsets terminated by a zero
sentinel, then concatenated FF8 single-byte text, each string running to the
next offset. The wiki names the script opcodes that reference them,
`SHOW_TEXT_BOX` (`0xFF1F`) and `SHOW_CHOICE_BOX` (`0xFF23`). They belong to the
world map rather than to a field, which is why they are not on the Text tab.

Measured on the installed file: 151 entries, offsets ascending from 608, one of
them a null string, and the rest the train and station dialogs the world map
shows — "`{Blue} {East Academy Station} {White}  Get off? Yes / No`", "Bound for
Timber. Pay 3,000 Gil to ride". Six entries carry a control byte `0x0D` that
neither the wiki's control-code list nor the kernel text codec names, so it
stays visible as `{x0D}` plus its argument instead of being given an invented
meaning.

`side_quest_texts` reads them and `tests/ff8/verify_ff8_world_texts.py` proves
the count, the ascending offsets, the sentinel, that each string ends at a
terminator inside its own span with zeros after it, the known dialog, the six
unnamed control bytes, and that an offset outside the section is refused.

Writing this section is not built: changing a string's length moves every later
section, so it needs the 48-entry pointer header rebuilt, which this plugin has
not done for any section yet.
