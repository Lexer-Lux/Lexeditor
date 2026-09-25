# World to field (wm2field.tbl)

`wm2field.tbl` is the other half of the field-to-world table: where a position
on the world map sends the player, one field ID per place. The plugin already
had the field-to-world direction (wmset section 9); this is the world-to-field
direction the editability audit listed as missing.

## Where it lives

Inside `Data/lang-en/main.fs`, entry `c:\ff8\data\eng\wm2field.tbl`. The plugin
extracts it to `baseline/en/main/wm2field.tbl` on first use, keyed by the
archive triplet's size and modification time, and writes a replacement to the
FFNx direct tree as `direct/wm2field.tbl`.

## Layout, read from the installed file

1728 bytes: 72 entries of 24 bytes.

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | signed 16-bit | X |
| 2 | signed 16-bit | Y |
| 4 | unsigned 16-bit | Z |
| 6 | unsigned 16-bit | field ID |
| 8 | 1 byte | one more value, unnamed here |
| 9 | 15 bytes | preserved, meaning not established |

Two facts of the file itself separate the coordinates from the IDs: the values
at offsets 0 and 2 are the only ones wider than a field ID (the widest is
10,215 while every ID stays under 1,200), and every ID falls in the range the
field archive uses. 67 of the 72 entries carry a distinct field ID.

## What the other tool adds

Rinoa's Toolset reads the same table (`SerahToolkit_SharpGL/wm2field.cs`, 72
entries of 24 bytes, signed X, signed Y, unsigned Z, unsigned field ID, one
byte at offset 8, then twelve bytes it does not name) and records that the game
multiplies the stored X and Y by 4096 before comparing them (`shl ecx, 0Ch`).
That scale is quoted from that tool, not measured here, and the page says so.

## Evidence for the writer

`plugins/ff8/wm2field.py` changes only the four named fields of an entry.
`tests/ff8/verify_ff8_wm2field.py` proves that an untouched table is written
back byte for byte, that editing two entries moves exactly the bytes of those
two entries' fields, that the byte at offset 8 and the fifteen bytes after it
survive untouched, and that the writer refuses an out-of-range entry, a
duplicate edit, a missing id, a non-numeric value, an out-of-range Z or field
ID and a truncated file.

## What is not claimed

What the byte at offset 8 means, what the fifteen tail bytes hold, and how the
game selects an entry from a standing position are not established here. The
table is edited as the game's own world-to-field list, with those bytes
preserved rather than guessed at.
