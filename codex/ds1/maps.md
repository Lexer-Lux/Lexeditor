# DS1R maps (MSB1)

35 files in `map/MapStudio/*.msb`, 2 KB to 406 KB each, stored raw
(no DCX wrapper). Layout facts come from the Apache-2.0 SoulsTemplates
MSB/MSB1 templates (see `plugins/ds1/credits.md`) and were verified by
reading every installed map file.

## File shape

No file header. Four params back to back, each starting with a
little-endian version that is always 0:

`MODEL_PARAM_ST`, `EVENT_PARAM_ST`, `POINT_PARAM_ST`, `PARTS_PARAM_ST`.

A param holds a version, an absolute offset to its ASCII name, a count
equal to entries plus one, that many minus one absolute entry offsets,
and the next param's absolute offset (0 ends the file).

## Models and parts

A model entry is 0x20 bytes: relative name and path offsets, a type,
an ID, an instance count, then three zero ints. Enemy models are named
`cXXXX` after their character folder. Observed model types: 0, 1, 2,
4, 5, 6.

A part entry is 0x64 bytes: relative name, path, entity (`+0x58`) and
type-data (`+0x5C`) offsets, position, rotation and scale as float
triples, eight group ints, and a final zero int. Positions are metres
and rotations are degrees, from measured value ranges (rotations are
stored unwrapped, past +/-180). Observed part types: 0, 1, 2, 4, 5, 8,
9, 10, 11. Type 3 (items) appears in no map file.

Part IDs repeat across types; the `(type, id)` pair and the part name
are each unique within a file.

## Enemy placements

Enemy types are 2 and 10 (2532 placements across all maps); player
starts are type 4 (77). Enemy type-data starts with two zero ints,
then think, NPC and talk IDs. 2495 of 2532 placements point at a real
NpcParam row; the rest keep IDs the parameter archive does not have.
The model index selects appearance (`cXXXX`); the NPC ID selects stats
and AI. They are separate fields and can disagree.

## Object placements

Object types are 1 and 9 (5481 placements across all maps); both use
`oXXXX` object models. Only position and rotation edit, through the
part header every part shares. No ObjAct row ID appears in object
type-data or entity words, so which lot a chest gives stays unmapped
and only the lots themselves edit, on the World tab.

## Duplicating placements

Type-data blob sizes from Part.bt, confirmed by reading every map:
enemy 0x40, object 0x18, player 0x10. All 8090 placement blobs
satisfy the template's fixed words (enemy: two leading zero ints,
zero at 0x15, zeros at 0x20/0x24; object: zeros at 0x00/0x0A/0x14
and -1-or-0 at 0x0E/0x10; player: 16 zero bytes).

Entity IDs are not unique in the wild: -1 (none) repeats everywhere
and some maps share positive IDs. A duplicate takes max-plus-one
unless its source is -1. The PARTS directory is rewritten at
end-of-file with the appended entry; existing entries keep their
bytes and indices.
