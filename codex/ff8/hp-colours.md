# FF8 smooth HP-number colours

Issue: GitHub #481.

## Renderer evidence

FFNx current master and the pinned combined derivative revision
`c056db2783f376a340fcefa6a48cc33618998876` both carry 8-bit BGRA on
`nvertex`. The normal FFNx fragment shader multiplies textured 2D colour by
that vertex colour. FF8 assigns `common_draw_paletted2D` to its paletted 2D
driver entry, so the renderer can produce true per-draw RGB; this does not need
palette stepping.

The supported Steam English executable remains SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.
The existing native verifier executes the shared character widget at
`004C0780` and observes its HP-number draw through native number renderer
`004A3530`, with the HP position packed as `((y+75)<<16)|(x+141)`. Existing
battle verification already establishes the HP row/glyph calls at
`004B17D5`, `004B1100`, and `004B127B`.

## Issue #481 seam

Better HP Colors is a default-off FFNx derivative switch. When on, the FF8
paletted-2D driver is wrapped, but the wrapper delegates unchanged unless a
verified native HP-number scope is active.

Battle reuses the existing row/HP-glyph hooks to obtain the same current/max HP
the HUD is drawing. Menus reuse the seven already-audited callers of the shared
character widget. The native number renderer is detoured only while that widget
runs; its original five bytes are restored before the native function executes
and after the widget returns. The original argument stack is preserved, and the
known packed HP position scopes the tint to the HP number.

The wrapper accepts only vanilla white/yellow palettes and untouched white RGB
vertices. Any other native palette/vertex colour wins. It temporarily uses the
white glyph palette plus the interpolated RGB, calls FFNx's normal paletted
draw, then restores the palette and vertices. KO (current HP zero) and full HP
do not activate the tint.

Piecewise RGB anchors are white `(255,255,255)` at 100%, yellow
`(255,255,0)` at 50%, orange `(255,128,0)` at 25%, and red
`(255,0,0)` at 0%. The mathematical zero endpoint is red, while live zero HP
is deliberately bypassed so KO keeps vanilla presentation.

Source/build tests establish interpolation, hook/config contracts and an
isolated binary candidate. They do **not** establish in-game rendering; use the
candidate's `ISSUE481-ACCEPTANCE.txt` for battle/menu visual acceptance.
