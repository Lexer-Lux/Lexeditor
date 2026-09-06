# Shared UI review and approved graph treatment

Open **Blank → Design Review**. The controls there are in-memory review fixtures:
they do not save preferences, change game data, launch games, or replace a plugin's
production layout.

## Shared layout (#99)

The two earlier menu-bar proposals were rejected. They are retired. The production
menu bar is intentionally unchanged while these new alternatives are reviewed.

**C — Tab-first compact header.** Keep the familiar horizontal game-section tabs
as the primary row. Put the current mod selector and Undo/Redo/Save/Play actions
in that same compact row rather than adding another redesigned menu strip. The
record list and editable properties stay below. The optional 3D preview is a
collapsible drawer inside the detail pane, so hiding it gives all width back to
properties. This preserves the existing navigation hierarchy while reducing
header height.

**D — Vertical workspace rail.** Move game-section navigation and the mod selector
off the menu bar into a narrow left workspace rail. Keep Undo/Redo/Save/Play in a
small command row immediately over the editor. The 3D preview becomes a
collapsible right drawer that falls below the editor at narrow widths. This frees
horizontal header space and keeps editing actions adjacent to the content they
affect.

Both alternatives keep Help, Information and Settings grouped beside the native
window controls. Neither is applied to the real shell until one is approved or
revised.

## Formula readability (#299)

**Design A is approved and implemented in the shared curve editor.** The formula
uses the active game/interface font at natural weight, a subtle shadow and a fully
transparent background. It follows the curve rather than sitting in a box or a
centered overlay. Powers are raised. Fraction markup is preserved as a stacked
numerator/denominator treatment when supplied, and minimum/maximum labels use the
same typographic treatment.

The curve editor measures the natural rendered formula width instead of stretching
character spacing to fill the path. Long expressions may reduce font size within
a readability floor and shift along the guide to avoid clipping. Invalid formula
results clear stale graphics, and extrema are computed from the evaluated curve
rather than assuming endpoints are ordered.

The Design Review page keeps position and multiplier sliders only to exercise the
approved treatment at different slopes; there is no remaining A/B typography
choice.
