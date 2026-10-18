# DS1 menu lists and the grid rework's raw material

Measured by read-only inspection of the Steam Remastered install (executable
SHA-256 `a45aaa36…71f98d7b`, `menu/menu.drb.dcx` SHA-256 `b7c52d98…3310cb96`).
Issue #728.

## List screens are 14-row text lists

`list_main`, `list_category` and `list_insert` each hold `button0_0` through
`button13_0`: dynamic text nodes (kind 2, length 128), one 30-unit row apart
(`list_main` rows run y 12–40 down to y 402–430, x 45–473), plus `cursor0_0`
through `cursor13_0` Null highlight rects over the same rows. The frame is
450 units tall, so the 14 rows fill it; more rows need shorter rows.

## Row content templates

`list_arms`, `list_armor`, `list_item`, `list_magic` and `list_arrow` are
single name-plus-stat-column layouts (one `text_param_name`, then icon and
value columns on a second line). The exe references these dialog names as
wide strings and instantiates them per row.

## How the exe addresses rows

Row node names are formatted at runtime: the exe holds wide `button%d_0`
and `cursor%d_0` format strings. Fixed `button0_0`…`button5_0`-style
literals also exist for menus with fixed rows. The 0–13 loop bound and the
up/down cursor math live in code; layout moves alone cannot add rows or
teach the cursor a second dimension.

## Already a grid

`T02_equip_list` (the equipment loadout) is a 2D icon-button grid with
exe-driven 2D navigation (`button0_0`…`button2_5` over icon frames). It is
not a rework target. The rework targets are the 1D text lists above and
the item-change screens built on them.
