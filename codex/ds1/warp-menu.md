# Bonfire warp menu

Measured by read-only inspection of the Steam Remastered install (executable
SHA-256 `a45aaa36…71f98d7b`, menu layout SHA-256 `b7c52d98…3310cb96`).

## Who owns the list

The warp menu is the executable's `FrpgMenuDlgWarp` dialog (RTTI at
`.data:0x1B27088`, vftable `.rdata:0x13C6C40`, object size `0x278`). Event
scripts carry none of its text IDs, so no EMEVD drives it. It draws DRB
dialog `F09`; the destination list is `F09-06` with 11 visible rows
(`button0_0`…`button10_0`) plus `scrollbar`.

Row `i` shows message ID `250050+i`, whose text is the tag
`<?warpName1?>`…`<?warpName11?>`. The tag names live in the executable as
wide strings (`.rdata:0x1377C80`, 13 of them; the 12th and 13th have no
FMG user). Registration code references them at `0x5419C3` and on. Each
tag resolves to the `Place_name_` text of one entry of the dialog's
destination vector, windowed by the scroll position.

## The destination table

`.data:0x1A325C0` holds 21 records of 12 bytes: `+0` an unlock parameter,
`+4` a bonfire entity ID, `+8` a `Place_name_` ID from 2000 (`Firelink
Shrine`) to 2020 (`Catacombs`) in order. That order is the list order:
vanilla shows destinations sorted by `Place_name_` ID, not by area.

`0x6ED740` (the dialog's event-`1004` handler) builds the shown vector at
`dialog+0x248`: 21 iterations (`mov r14d, 0x15` at `0x6ED7D4`), each
calling the unlock check `0x4F57A0` with `+0`, skipping the record whose
`+4` equals the current-bonfire global at `0x1A326BC`, and appending the
survivors through `0x6EE860`. The count lands in `dialog+0x218` and in DL
property 3003. The two table pointers come from adjacent 7-byte `lea`s at
`0x6ED7C6` (`48 8D 1D F7 4D 34 01 48 8D 3D EC 4D 34 01`).

Because locked and current destinations are skipped, the shown vector is
normally shorter than the table, so selection, confirm and travel must
follow the vector, not the table. Reordering the table changes only the
shown order: every record keeps its unlock parameter, entity and name.

Confirm and empty states are `Dialogue_` 18000 (`Warp to selected
bonfire`) and 18001 (`No bonfires available for warping`), shown from the
dialog's event-`1017` branch (`mov edx, 0x4650/0x4651` in `0x6ED340`).

## Later games

Dark Souls III keeps the same dialog classes (`FrpgMenuDlgWarp`,
`FrpgMenuDlgWarpPlate` in DarkSoulsIII.exe), but its menus are Scaleform
GFX (Flash) inside encrypted BDT archives (Data1 unpacked with
BinderTool), so nothing transfers as files to DS1's DRB layouts. The
travel screen is `menu/02_080_warp.gfx`: a 14-row `WindowList`/`ItemList`
with per-row icons (`ItemIcon`, `MENU_WarpIcon` atlas), an L/R-navigated
`TabList` with highlight, title, key guide and status bar. The 58
`menu/mapimage` textures (`MENU_MapImage_10001`…, 512×256) are one vista
per area, loaded by formatted ID for the loading screen
(`MENU_MapImage_%05d`, `MENU_Common_LoadingMapImage` in the executable);
the travel list itself carries no pictures. The bonfire menu
(`03_002_bonfire.gfx`) is a plain list with no tabs or icons. The
shipped DarkSoulsIII.exe is DRM-scrambled on disk (zero data
directories, sampled `.text` high-entropy), so its warp methods need a
runtime dump; static analysis stops at RTTI and strings. Dark Souls II
uses an unrelated `Fe` menu framework (`FeGroupTestBonfireTop`,
`FeGroupTestBonfireTransitionList`/`Top` for travel).
