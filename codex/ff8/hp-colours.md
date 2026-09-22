# FF8 smooth HP-number colours

Issue: GitHub #481.

FFNx carries 8-bit BGRA on `nvertex`; its normal 2D shader multiplies textured colour by vertex colour. FF8 routes paletted 2D through `common_draw_paletted2D`, so true per-draw RGB is available without palette steps.

Supported Steam English `FF8_EN.exe` SHA-256:
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.

Executable-backed verification establishes battle row/HP glyph calls `004B17D5`, `004B1100`, `004B127B`, seven callers of shared character widget `004C0780`, and its HP-number draw through `004A3530` at packed position `((y+75)<<16)|(x+141)`. The shared widget's 32-byte computed-stat argument uses words 4/5 for displayed current/max HP, matching current main-menu HP-gauge work.

Better HP Colors is default off. When requested, the FF8 paletted driver selects a wrapper, but it delegates unchanged until every verified battle/shared-widget identity matched and an HP scope is active. Battle reuses the verified HP glyph scope. Shared character panels temporarily enable the `004A3530` detour only while that widget executes; the known HP position is checked and the native function is restored while it runs.

Only native white/yellow palette batches with untouched white vertex RGB are eligible. Other palettes or pre-coloured vertices win. Eligible batches temporarily use white glyphs multiplied by the interpolated RGB, call FFNx's normal paletted draw, then restore palette and vertex bytes.

Anchors: white `(255,255,255)` at 100%, yellow `(255,255,0)` at 50%, orange `(255,128,0)` at 25%, red `(255,0,0)` at 0%, piecewise linear. Live 0 HP bypasses tinting so KO remains vanilla; full HP also delegates unchanged.

The active main-menu rows call `004BF380` at `004C1DF6` and `004C1F78` with current/max HP and the native status palette. Its current-number call is `004BF407` to `0049F850`; the slash and maximum use separate calls. The reserve widget `004C2090`, called at `004C1AED`, draws current HP at `004C22CD`. Its digit coordinates are `(107+120*column, 124+24*row)`, with character IDs in menu-state bytes `0x38+2*row+column`. Computed HP uses words 4/5 at `01D771B0+32*id`. These calls are checked before colour hooks are installed. Native status and KO palettes retain priority. Source/build checks are not live visual acceptance.
