# Field background and walkmesh projection

The CA position words are view translation values, not a world-space eye
position. Recover the eye in raw vertex units as `-R^T * position / 4096`.
Use the normalized third camera axis as forward and the negated second axis
as up. Normalize the side vector from their cross product. Project both
screen axes with the same depth and camera zoom.

MAP tile coordinates are centred on the screen origin. The background
renderer moves them by `bounds.left` and `bounds.top` to form the image.
Apply these offsets once to the projected walkmesh. Do not add another
160/112 screen-centre offset: that shifts the mesh right and down by half
the game screen.

The background and overlay must share one image rectangle and aspect ratio.
Camera edits move the projected geometry; the painted background remains
fixed. BCCENT12 provides a useful visual check: walkable bridge triangles
align with its road and side paths.

Reference: [Deling WalkmeshGLWidget.cpp](https://github.com/myst6re/deling/blob/master/src/3d/WalkmeshGLWidget.cpp),
particularly `paintGL`, `computeFov`, and `drawBackground`. Deling is already
credited in the FF8 Credits. Local checks cover the view translation,
uniform axis scale, image bounds, and shared preview rectangle in
`tests/ff8/test_ff8_field_panel_layout.py` and `test_ff8_field_geometry.py`.
