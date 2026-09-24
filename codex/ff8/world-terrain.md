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
