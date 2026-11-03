# DS1R map rendering data

These facts were checked against installed Remastered models, textures and
material binders. The reader and renderer use synthetic regression fixtures;
the repository does not contain the sampled game assets.

## Surface textures

`g_Bumpmap` does not universally mean a three-channel RGB normal map.
The Gaping Dragon's `c5260_n` stores its two normal components in R/G and
has zero blue throughout the sampled texture. Reconstruct positive Z from
the two components; treating blue as Z turns its shading backwards.

The Depths' `m10_water` is grayscale, including equal R/G/B samples, and is
used as a height field by `[We]` water materials. It has no diffuse texture.
Waterfalls can have a diffuse plus an ordinary packed normal texture, so
matching the word "water" alone does not identify a height field.

Diffuse pixels are color data; normal vectors, heights and baked-light
values are linear data. Their texture objects need separate roles even
when they share a PNG. Baked light uses the second UV set. Some lightmap
UVs contain whole-tile offsets, including U near -31 in the Depths;
repeat wrapping retains their atlas location, whereas clamping smears
an edge texel into a band.

## Material definitions

The installed `mtd/Mtd.mtdbnd.dcx` and `MtdPatch.mtdbnd.dcx` use BND3 header
word `0x54` and 24-byte member records, including the unpacked-size field.
Do not infer a 20-byte directory just because the word is not `0x74`.
The shared binder reader and repacker preserve this width.

Material definitions provide `g_WaterColor` (four floats),
`g_WaterWaveHeight`, `g_SpecularPower` and additional shader parameters.
Sewer variants using the same `m10_water` height texture have different
color/alpha values. Texture identity alone therefore cannot key their
rendered materials. The material-binder source/stamp must also invalidate
both memory and disk geometry caches when it changes.

MTD block/string layout was cross-checked with the
[SoulsFormats MTD reader](https://github.com/JKAnderson/SoulsFormats/blob/master/SoulsFormats/Formats/MTD.cs).
The independent bounded reader decoded all 592 definitions exposed by the
two installed binders, including 51 with a water-color parameter.

## Rigid mesh transforms

Static FLVER meshes may use bone-local coordinates. The Depths'
`m2080B0` mesh 9 is such a decal: its local vertices sit near zero, while
its assigned bone translates it to approximately (-94.97, -74.02, -36.16).
Ignoring that transform strands the decal near the origin and expands
the model's camera-framing bounds. Apply the rigid transform when preparing
viewer geometry, without modifying the model's source positions.
