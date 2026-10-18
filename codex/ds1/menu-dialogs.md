# DS1 menu dialogs: input, DL events, tabs

Measured by read-only inspection of the Steam Remastered install
(executable SHA-256 `a45aaa36…71f98d7b`, menu layout SHA-256
`b7c52d98…3310cb96`). Complements `codex/ds1/warp-menu.md` (warp list
ownership) and `codex/ds1/menu-layout.md` (DRB structure): this page is
how dialogs read input, talk to each other, and what the tab widgets do.

## Vtable roles

`FrpgMenuDlg*` dialogs share slot meanings (indices verified on Warp,
Inventory, EquipList and both tab classes):

- `[16]`: draw. Reads live state every frame (the warp draw rebuilds
  all row texts from the destination vector; tab draws read DL-set
  fields and global state channels).
- `[27]` (offset `0xD8`): DL-event router. Signature `(this, event,
  arg)`; `arg` is a typed value (`+8`: 2 = int at `+0`, 1 =
  float-to-int, 3 = refcounted object). Every router calls its base
  router first, then switches on its own event IDs.
- `[35]`: list-widget callback. `(this, code, row, ...)` with small
  codes (warp: 2 = decide row, 8 = focus row, 0xC = move) and
  `row - 0x64` the vector index, range-checked against the count.
  Inventory also accepts `0xC8`-based rows and `0x2710`-based tab
  clicks (below).
- `[36]`: per-frame update. Polls raw buttons through `0xED6750(this,
  id)` and drives movement, decide/cancel and submenu calls.
- `[40]` on list dialogs is the shared `0x6615A0` (detail refresh).

## Button IDs (`0xED6750`)

Polled sets were surveyed across every `FrpgMenuDlg*` vtable; roles
from what each handler does with the result:

| ID | Role | Evidence |
| --- | --- | --- |
| `0x86` / `0x87` | Up / Down | First polls everywhere; feed `0x6612A0` move with direction 1 / 0 |
| `0x88` / `0x89` | Up / Down repeat pair | Shops/warp poll after the first pair |
| `0x8A` / `0x8B` | Up / Down alternate (stick) | OR-ed with `0x86`/`0x87` by inventory, shops, equip lists |
| `0x8E` / `0x8F` | Second Up / Down pair, fast flag | Feed move with `r8 = 1` (vs 0); physical binding unmapped |
| `0x96` / `0x97` | Decide / Cancel | Warp: `0x96` selects (`0x6EDEF0`), `0x97` runs the close sequence also used by the manager cancel path |
| `0x98` / `0x99` | Left / Right d-pad | Warp aliases them to up/down; inventory uses them as the grid's second axis |
| `0x9D` / `0x9E` | Tab/page pair (L1/R1 by menu role) | Polled only by tabbed or paged menus: Inventory, Equip, EquipList, IngameStatus, StatusRefParam, FaceEditPreview, DispOption, SoundOption. Flat menus (warp, shops, box, talk) never poll them |
| `0x9A` | Unmapped | Polled by nearly every menu including warp; effect unknown |

In DS1, L1/R1 (`0x9D`/`0x9E`) switch top-level start-menu screens
through the `0x66E330` → `0x66E3F0` state machine (cases close every
screen, open one, record it with `0x71ABF0(0x4B, n)`). Inventory
category tabs switch with d-pad Left/Right through grid movement.

## DL events between dialogs

One dialog addresses another by control name: `0xED6020(dialog,
name)`, then `[control + 0xD0]` for its dialog, then the `[27]`
virtual (`0xD8`) with the event ID and a typed arg. Precedents:

- Inventory tab click: `[35]` receives `0x2710 + index`, looks up
  `tab_select`, sends DL `2027` with the index.
- `FrpgMenuDlgCommonTab` draw sends DL `5000` with its index field to
  `icon_select` and sets the `text_title` tag from FMG text.
- A dialog re-sends to itself the same way (inventory DL `2515`
  re-dispatches `1001`).

Event scripts configure tabs the same way (`TurnToFacePlayer` in the
decompiler is a DL send). The box ESD opens two `FrpgMenuDlgEquipListTab`
children (`I01_tab_select`, `I01_repository_tab_select`) then sends
each: `3017, 0` (init), `3018, count` (8 and 14 tabs), `1009, index`
(selected tab). `EquipListTab[27]` stores DL `1009`'s arg at
`+0x210`; `3017`/`3018` pass through to its base router. Its other
own IDs are `2022`–`2024`, `2026` (stored at `+0x264` with a refresh
call), `2027`, `3019`, `5000` (stores a state-channel ID at `+0x260`
and binds the `tab_cursor` control) and `5004`. The `2027` and `3019`
handler bodies were not fully read.

## Tab strips are icon-only

Every `*_tab_select` DRB dialog is the same kit: `tab_cursor0_N`
anchors, `ItemIcon0_N` sprites, `tab_changeover_N` highlight sprites,
`blackout0_N` dim sprites and a `tab_cursor` child. No tab strip has a
text node. Slot counts: repository 14, inventory 8, shop 7, repair 2,
R13/R15 3. A text tab strip needs new layout nodes (see below); the
icon strips cannot show text and top out at 14 slots.

`FrpgMenuDlgCommonTab` is a thin DLG-animation wrapper around an
`FrpgMenuDlgObjItemSelect` child plus a title; it is not a reusable
text tab strip.

## Warp screen geometry (DRB `F09`)

- Root `F09`: `BG` plate dialog, `F09-06` (the warp list, full-screen
  rect) and the parked off-screen variants `F09-00`…`F09-04`.
  `F09-05` (title plate `plate_menu-tab` + `text_title` + `icon`) is a
  Null entry, not instanced by the warp flow.
- `F09-06` rows `button0_0`…`button10_0` span x 138–483, y 191–519 at
  a 30-unit pitch, left-aligned (align 8). Frame `F04_frame_PC`
  (67, 64, 497, 664), key guide (99, 582, 524, 618), scrollbar at
  x 127–137. Nothing on the right half belongs to the warp dialog.
- `map_shot` is a textureless sprite parked off-screen at
  (−808, 980, −307, 1212). No executable code references it.

New text nodes copy a row's rectangle; a horizontal strip above the
list (y ≈ 131–159) and a right-side panel both need horizontal
placement `compose` does not offer (it moves nodes vertically only).

## Useful routines

- `0xED6020(dialog, name)`: child control by wide name (above).
- `0xEDBD90(control, text)`: set dynamic text; forwards `text` to the
  control's `[0xC8]` setter. `0xEDBDB0(control, bool)` sets
  visibility (both previously noted in `menu-layout.md`).
- `0x53DC80(msgid)`: `Place_name_` text; the warp draw calls it with
  each vector record's `+8`. Sibling getters `0x53D4C0`/`0x53DB30`
  serve other FMG banks (`+0x3E0`/`+0x3C0`). Every getter reads one bank
  pointer from the message repository `[0x1C7E3E8]` and asks the leaf
  `0x53DF10(bank, id)`, which returns the entry's wide string or 0; the
  getter itself then builds a `?Bank? ID: %d` fallback on the heap.
  GoodsName is bank `+0x380` (getter `0x53B650`, whose fallback label is
  `?GoodsName? ID: %d`). An island wanting a goods name calls the leaf
  directly and handles 0 itself.
- `0x66F4A0`: the start-menu root update (category strip, four icons,
  close on cancel). Its only caller (`0x66EF07`) hands it the `R00-00`
  dialog, the same object it looks up `R00-00`'s own `plate_black` on,
  so nodes added to `R00-00` resolve with one `0xED6020` from it. The
  `category_LR` strip inside it is a sub-dialog instanced by twelve
  menus; `0xED6020` on a sub-dialog's control does not search inside it.
- Inventory entries (`player data + 0x280`, layout in
  `codex/ds1/ammunition-hud.md`) start with a category word,
  `category << 28`: weapons 0, armour `0x10000000`, rings `0x20000000`,
  goods `0x40000000` (`0x3F2800` decodes it; `0x6AEAD1` switches on it).
  The inventory Use `0x6AE920(listDialog, index)` passes goods through
  its can-use check `0x6AECD0` unconditionally.
- `0x4F57A0(flagManager, id)`: event-flag test (`0x2C8940` returns the
  manager). The warp builder calls it with each record's `+0`.
- `0x6612A0(this, direction, fast)`: shared list move. Fields:
  `+0x208` count, `+0x214` cursor, `+0x21C` scroll, `+0x218` record
  total (builder-set), `+0x224`/`+0x225` dirty flags. Rebuilding a
  list must reset cursor and scroll; the builder does not.
- `0x723620(code)`: global menu helper (codes 0, 100, 200, 300);
  `0x63AA00` tail-calls it. `0x71ABD0`/`0x71ABF0` read/write global
  menu state channels.
