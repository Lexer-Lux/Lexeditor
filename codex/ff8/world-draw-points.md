# World draw points: where they are, and what they give

Settled facts behind the World page's Draw Points subtab and the Draw Points it
shares with the Map page. Source: the FF8 modding wiki's wmset reference and its
ExeData page on draw points, both credited in the plugin's Credits
(`ui/credits-sources.json`, ff8). Surveyed 2026-09-25.

## The file holds the trigger position

`wmsetus.obj` section 34 is a fixed table: a `0x2C`-byte header, then 128
four-byte records in draw-ID order.

| Offset | Field | Meaning |
| --- | --- | --- |
| 0 | `x` | Block column |
| 1 | `y` | Block row (twice this value plus the top bit of `x`) |
| 2 | `sub_id` | Location discriminator |
| 3 | padding | Always zero |

The first `0x28` bytes are a five-entry block table, each entry a start and end
byte offset into the record array: `[0x2C,0x200)`, `[0x200,0x204)`,
`[0x204,0x208)`, `[0x208,0x210)`, `[0x210,0x228)`, which are the record ranges
`0..116`, `117`, `118`, `119..120`, `121..126`. The runtime picks one block per
world region through a small region-to-block table in the executable, so only
the draw points in the player's region are scanned. Because records never move,
editing one in place keeps the block table valid.

## How the game finds the record

When the action button is pressed, the runtime scans the current region's block
for the record whose block id (`x`, `y`) matches where the player stands **and**
whose `sub_id` equals the current location index, and uses that record's number.
That number plus 128 indexes the executable's draw-point data, which is what the
game then gives the player.

Two consequences a reader of the editor needs:

- `sub_id` is not a free number. Several draw points share a block - on the two
  islands block `(113, 10)` carries three, with sub-IDs 15, 27 and 33 - so the
  sub-ID has to be the location index the game uses there. Copy it from a draw
  point that already works in that block.
- Which record a spot resolves to decides what it gives, so moving a draw point
  into another block changes what the player gets there.

## The magic lives in the executable

`DrawPointData` is a 256-byte array in `FF8_EN.exe`, one byte per draw point:

| Bits | Field |
| --- | --- |
| 0-5 | Magic ID |
| 6 | Refill (the point fills again after being drawn) |
| 7 | High yield (draws more than ten) |

`DrawPointStatus` holds two bits per draw point in memory for its current state
(0 fully stocked, 1 partly, 2 empty but refills, 3 empty forever).

There is no per-draw-point **quantity** in either table: the only amount the
game stores is the high-yield flag. Lexeditor does not write the executable, so
this page moves draw points and cannot change what they give.
