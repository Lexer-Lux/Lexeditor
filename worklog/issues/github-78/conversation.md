# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5311959908 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/78

Created: 2026-09-01T12:42:38Z; updated: 2026-09-04T12:25:09Z

Exact metadata: [source record](sources/issue-5311959908-f91df7e75aead1791eb27534e89c3660e7bf41f09fdd623ea8556ee17f96ae02.json).

The item detail panel's icon slot currently runs a live WebGL canvas showing the item's `inventoryMesh` from the same free-look camera as the full preview below it. It reads as a dark, badly-framed micro-render rather than an icon.

Warband ships no 2D item icons — verified against the install: `Textures/` holds 1269 `.dds` files and all are 3D materials (`_normalmap`, `_specular`); the only icon-named files are `map_icons.dds` (world-map party markers) and `mouse_icon.dds`. The game renders item meshes into inventory slots at runtime, so a render is the right source; it just needs to look like an icon.

Build a cached thumbnail pipeline:
- Render each item's `inventoryMesh` offscreen with a fixed three-quarter camera, a consistent key light, the mesh auto-fitted to the frame, on a neutral ground.
- Cache one PNG per mesh; serve it from `/api/item-icon`.
- Generate in the background on first start so it is unnoticeable.
- Key the cache on the source `.brf` file's size and mtime (plus the mesh name) so installing a mod that swaps meshes/textures or adds items regenerates only what actually changed, and different modules keep separate icon sets.

Not a priority.

## issue 5311959908 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/78

Created: 2026-09-01T12:42:38Z; updated: 2026-09-06T13:31:00Z

Exact metadata: [source record](sources/issue-5311959908-1b4ed3326b41d41c4647b28425ba861ae4475867caad03110b682161dcc7b291.json).

**Actionable — delivery remains.** Draft PR #361 adds fixed-camera PNG icons, background generation and module-separated caches. It is not merged; real-item framing and generation speed remain unverified.

Icons must regenerate when source assets change, fit boots through long polearms, and keep browsing responsive. The larger interactive preview remains. A ready-to-run test copy and disposable asset-change fixture still need preparing.
