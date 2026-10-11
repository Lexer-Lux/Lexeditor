# DS1 equipment-list menus

Measured by read-only inspection of the Steam Remastered install
(executable SHA-256 `a45aaa36…71f98d7b`, `menu/menu.drb.dcx` SHA-256
`b7c52d98…3310cb96`), plus in-game screenshots. Issue #728.

## The weapon-change list is data_list

`data_list` holds the background, five `list0`..`list4` Dialog row
hosts, `Equip_line_1`..`Equip_line_8` separators and a frame. Each row
hosts one `list_arms`-family instance: icon, name and six stat columns
(physical/magic/fire/lightning, durability, weight on the weapon
screen). Five visible rows is layout-driven. Rows are addressed with
the wide `list%d` format; separators have no name users (static decor).

## Dialog classes and their tables

This build's RTTI uses 32-bit RVAs: a Complete Object Locator is
signature/offset/cdOffset plus type-descriptor and class-hierarchy
RVAs, and vftable slot −1 holds the locator's address. Dialog classes
(`FrpgMenuDlg*`, `@NS_FRPG@@` namespace) and their vftables include:

- `FrpgMenuDlgEquipList`, vftable `0x13A2070`: slot 16 (`0x634A40`)
  binds rows; slots 27/35/36/38 (`0x634C40` event dispatcher,
  `0x634EB0`, `0x636CC0`, `0x635200`) are the cursor candidates.
- `FrpgMenuDlgEquipWepList`, vftable `0x13A7688`: slots 0/1
  (`0x652EE0`, `0x653E60`), 16 (`0x653180`), 27 (`0x652FB0`), 37–39
  (`0x653E20`, `0x653F60`, `0x653FA0`).
- `FrpgMenuDlgEquipListTab`, slots 27/28/37 (`0x63C2C0` row binder,
  `0x63C670`, `0x63DE80`): the tab strip inside equip lists.
- `FrpgMenuDlgEquipment`, vftable `0x13A1600`: the loadout icon grid.
- Every list dialog (Listbox, Warp, Inventory, shops, …) shares slot
  40 (`0x6615A0`): a per-row updater formatting the row name from
  dialog+0x210/+0x214, resolving container and row, attaching content
  and setting visibility.

## Name-only lists

`list_main`, `list_category` and `list_insert` hold 14 `button0_0`..
`button13_0` text rows plus `cursor0_0`..`cursor13_0` highlight rects
(see `menu-lists.md`). Tab strips use `tab_cursor0_N`, and `data_list`
uses `list0..N` dialog rows instead.
