# The game's own name list (namedic.bin)

`namedic.bin` holds the names and words the game's own text inserts: the world
places (Galbadia, Esthar, Balamb, Dollet, Timber, Trabia, Centra, Fishermans
Horizon, East Academy, Desert Prison, Trabia Garden, Lunar Base, Shumi Village,
Deling City, Balamb Garden, East Academy Station, Dollet Station, Desert Prison
Station, Lunar Gate, Ultimecia Castle, Garden, Deling) and the tutorial and menu
words (Restores, status, learns, ability, Magic, Refine, Junctions, Raises,
command, Magazine).

## Where it lives

The Steam release keeps it inside `Data/lang-en/main.fs` under the archive entry
`c:\ff8\data\eng\namedic.bin`; there is no loose `Namedic.bin` in the install.
The plugin extracts it to `baseline/en/main/namedic.bin` on first use, keyed by
the archive triplet's size and modification time, and writes a replacement to
the FFNx direct tree as `direct/namedic.bin`.

## Layout, proved from the installed file

The shipped file is 408 bytes:

| Field | Size | Value |
| --- | --- | --- |
| entry count | 16-bit little-endian | 32 |
| byte offsets | count × 16-bit little-endian | the first is 66, the end of this table; each is greater than the one before |
| names | one per offset, to the next offset (or the end of the file) | null-terminated FF8 single-byte text |

The last name carries two zero bytes after its terminator. Nothing else is
unexplained: the table's first offset equals its own length, the offsets
strictly increase, and every name decodes with the same FF8 text table the
kernel text uses.

## Evidence for the writer

Decoding all 32 shipped names with `plugins/ff8/kernel_text.py` and encoding
them again reproduces the stored bytes exactly, so a name of a different length
is written by rebuilding the offset table: `plugins/ff8/namedic.py` does that,
and `tests/ff8/verify_ff8_namedic.py` proves that a rewritten file keeps every
name the caller did not touch byte-identical, that the offsets move by exactly
the length change, and that the writer refuses a duplicate edit, an index
outside the list, an unrepresentable character and an embedded null.

Because the offsets are 16-bit, the whole file must stay under 65536 bytes:
the writer refuses a list that would grow past that rather than truncating it.

## What is not claimed

Which text opcodes read which entry is not established here. The list is edited
as the name list the game's own text uses, not as a mapping from an entry to
the messages that show it. Rinoa's Toolset edits the same table; the layout
above is this plugin's own reading of the installed file.
