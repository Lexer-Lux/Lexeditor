# World terrain coordinates

`world/dat/wmx.obj` has 0x9000-byte segments. The base map uses the first
768 segments in 32 columns and 24 rows. Each segment has 16 blocks arranged
in four columns and four rows. Variant segments follow the base map.

For a base-map segment `s` and block `b`, vertex coordinates in block units are:

- X: `(s % 32) * 4 + b % 4 + stored_x / 2048`
- Height: `((128 - stored_y) & 0xffff) / 2048`
- Z: `(s // 32) * 4 + b // 4 - stored_z / 2048`

The unsigned wrap in height is deliberate. Do not treat stored Y as a plain
positive elevation. Variant segments need their replacement position before
they can be placed on the base map.

Each polygon has three vertex indices, three normal indices, three byte UV
pairs, a texture byte (page in the high nibble, palette in the low nibble),
ground type, and two flag bytes. Block vertex indices are local to the block.

Sources:
[Deling WorldmapGLWidget](https://github.com/myst6re/deling/blob/master/src/3d/WorldmapGLWidget.cpp),
[Deling WmxFile](https://github.com/myst6re/deling/blob/master/src/game/worldmap/WmxFile.cpp).

`segment_mesh` in `plugins/ff8/world_geometry.py` reads these fields without
writing them. Tests use known block coordinates, UVs, material bytes, invalid
indices, and height wrap. Reading all 768 installed base segments on 2026-09-24
produced 357,862 vertices and 473,193 triangles.

## Placing a world coordinate on the map image

The sky/fog zones and the field-to-world records store signed world coordinates
rather than the packed block ids the draw points use. A world coordinate lands on
the map image at

- column = `x / 2048 + 64`
- row = `z / 2048 + 48`

in the 128 by 96 block grid: 2048 stored units to a block, as the vertex formula
above divides by, and the grid centred on the origin.

Evidence, 2026-09-25: the game's own minimap texture (wmset section 38) is 21.8%
land, and this transform puts 50 of the 64 field-to-world records and 7 of the 8
sky zones on or beside land. The misses are the all-zero records - the map centre
is ocean - plus one outlier at the bottom-left corner. Searching the four
axis-and-sign orders against every integer offset from -128 to 128 chose this one
by a wide margin: the runners-up managed 45, 40 and 39 of 64 with their own best
offsets, and 1024 units to a block managed 26 at best.

The transform is a fit to the terrain, not a rule read out of the engine: it is
strong enough to place a marker, and it should be revisited if a source ever
states the conversion directly.
