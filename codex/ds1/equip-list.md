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
Row geometry: `list0`..`list4` are full-width 80px rows at y 0/100/200/300/400
inside a 638x494 BG.

## The engine is already 2D

Slot 40 (`0x6615A0`, shared by every list dialog) formats the wide
`cursor%d_%d` name from (`[this+0x214]`, `[this+0x210]`): row, column.
`0x6617F0` computes the item id as `row * [this+0x20C] + col`, so
`+0x20C` reads as the row stride (1 in single-column lists, set at
`0x632733`; 2 at `0x6326DD`). `T02_equip_list` (the loadout screen) ships
`button{0..2}_{0..6}` and `icon_frame{r}_{c}` grids, and `I02-00` (the
equipment list's icon mode) ships a 3x7 `cursor{r}_{c}`/`button{r}_{c}`
grid: 2D stride, 2D cursor names and 2D input are all live in vanilla.

`EquipList[44]` (`0x6352B0`) is the list initializer: it finds
`Ins_data_list`, then loops rows binding `list%d` and `button%d_0`
(indices from the start index up to `[this+0x208]`); `EquipList[16]`
(`0x634A40`) loops the same bound binding `data_tab_%d`. A missing row
widget hits an assert (`int3`), so any extra rows need real DRB nodes.
`EquipList[27]` (`0x634C40`) dispatches input events (0x3E9/0x3EC/0x3EF,
0xA28/0xA2A, 0x1388) to the base handler plus helpers.

Display modes (Square/X) already re-bind the list with different
geometry: `I02-00` icon grid vs `I02-02` detail list (`cursor0_0`..
`cursor4_0` icon strip, `list_cursor0_0`..`list_cursor4_0` row
highlights, `button0_0`..`button4_0`, `data_tab_0`..`data_tab_4`). The
`+0x208`/`+0x20C` fields are per-class: on the list widget the row loop
is bounded by its count field; the parent screen keeps mode/count
(a 4/5/6 toggle state machine at `0x6310C0`, table-driven coords from
`0x13A0D80` via `0x630194`, `id = [0x214]*[0x208]+[0x20C]` at
`0x631940`). No hardcoded `cmp 5` bounds any list loop.

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
