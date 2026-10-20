# Menu layout (DRB) and the weapon detail screen

Measured by read-only inspection of the Steam Remastered install (executable
SHA-256 `a45aaa36…71f98d7b`). `plugins/ds1/menu_layout.py` reads and extends
this format; its tests use a synthetic file with the same encodings.

## Which file the game uses

The executable names `menu:/menu.drb`. Remastered reads
`menu/menu.drb.dcx` (194,527 bytes, SHA-256 `b7c52d98…3310cb96`; DFLT DCX
holding a 998,464-byte DRB). A loose `menu/menu.drb` (806,672 bytes) also
ships. It has fewer dialogs (531, not 638) and looks like the Prepare to Die
layout. Its geometry for the weapon panel happens to match. Do not read it as
the Remastered layout.

## DRB structure

A 16-byte header (`DRB\0` and zeros), then these sections in this order, each
a 16-byte header (tag, data length, count, 0) and data padded inside its
length to 16 bytes:

`STR TEXI SHPR CTPR ANIP INTP SCDP SHAP CTRL ANIK ANIO ANIM SCDK SCDO SCDL DLGO DLG END`

- STR: UTF-16 names, referenced by byte offset.
- SHAP / CTRL: 8-byte entries (type-name offset, data offset into SHPR / CTPR).
  One per object and per dialog. Vanilla stores them in serialization order
  (a dialog's own, then each of its objects') and the two tables are parallel.
  Every entry is used once.
- DLGO: 32-byte objects: name, SHAP offset, CTRL offset, five zero ints.
- DLG: 64-byte dialogs: name, SHAP, CTRL, five zero ints, object count and
  DLGO offset (fields 8 and 9), then width and height as shorts. A dialog owns
  a contiguous run of DLGO. Nothing else points into DLGO.
- The game finds a child by name: `0x140ED6020(dialog, wchar_t *name)`. Text
  is set with `0x140EDBD90(node, wchar_t *)` and visibility with
  `0x140EDBDB0(node, bool)`.
- For a dialog with no text node of its own (the start menu's `R00-00`), a
  layout text node names a source dialog with `from` and copies that
  dialog's node bytes, its rectangle moved by `dx`/`dy` into the target's
  space. Clones take `from` the same way.
- New nodes go at the end of their dialog unless they name `before`, an
  existing node they are inserted in front of (its DLGO entry, shape and
  control references shift along). Nodes appended last were drawn on top in
  the start menu (Tool Belt v2, 2026-10-17); `before` puts a plate under a
  dialog's own content.

### Text shapes

Bytes 0–7 are left, top, right, bottom (int16). Bytes 8–29 hold style: in
every weapon-panel text they read `-1, -1` (int16 pair), int32 0, `01 01 00
00`, a small int32 (3 or 7), a 4-byte colour and `07 00`. Byte 30 is the
alignment: labels use 8, numbers 9 and the scaling letters 10, so probably
left, right and centred. Byte 31 is the kind. After the kind comes `0x1C`
(int32) and:

- kind 1, message text: char length, message ID, six zero bytes (50 bytes).
  The label is fixed from the menu messages; Stability is message 102125.
- kind 2, dynamic text: maximum length in characters, six zero bytes
  (46 bytes). Empty until the game sets it. `text_attack_m_d` holds 16
  characters at most.

All 1,167 message and 608 dynamic text shapes in the file follow these forms.
Kind 0 also occurs (46 bytes) and was not decoded.

## Weapon detail panels

Three dialogs show a weapon's stats: `data_simple_arms` (the detail screen),
`I01_data_simple_arms` and `C01_data_simple_arms`. Rows are 30 units apart.

| Panel | Last attack row (Critical) | Stability | Free slot under both |
| --- | --- | --- | --- |
| `data_simple_arms` | `text_attack_d` / `text_param_attack_d`, y 261 | `text_receive_name` / `text_param_receive`, y 262 | y 291–320, header at 322 |
| `I01_data_simple_arms` | `text_attack_d` / `text_param_attack_d`, y 197 | y 197 | y 227–255, header at 257 |
| `C01_data_simple_arms` | `text_attack_fatal` / `text_param_attack_d`, y 252 | y 252 | y 282–311, header at 316 |

The left free slot holds the game's spare row `text_attack_m_d`,
`text_param_attack_m_d` and `text_param_attack_m_d_add` in the first two
panels. Bows and catalysts use it. `C01_` has no spare row. **The right
column has no node at all under Stability**: adding a stat there needs new
layout nodes.

## Weapon update dispatch

The code just before `0x1406496D5` picks one of three routines for the
selected weapon, all called as `(dialog, weapon id, float)`, then joins at
`0x1406496DA` (RVAs below):

| Call site | Routine | Taken when |
| --- | --- | --- |
| `0x6496D5` | `0x64AB10` | default, and when there is no weapon data |
| `0x6496B6` | `0x64BFC0` | byte 0x100 ≥ 0x80, or byte 0x101 has bit 0, 1 or 2 set |
| `0x64969A` | `0x64B6E0` | otherwise, when byte 0xE2 is 10 or 11 |

The bytes are offsets into the weapon's parameter row. Which weapon classes
each branch serves was not mapped; bows and catalysts take the two non-default
branches.

Each routine walks the row's 12 value nodes with a visibility table. For
`0x64AB10` it is `01 01 01 01 01 00 01 01 01 01 00 00`: it hides
`text_param_attack_m_d`, `text_param_attack_d_add` and
`text_param_attack_m_d_add`. It sets the sixth label (`text_attack_m_d`) from
message ID 0, which leaves it empty.
