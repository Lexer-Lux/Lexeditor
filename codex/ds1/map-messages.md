# DS1 developer soapstone messages (MSB event type 6)

Measured by read-only inspection of the 17 installed Remastered maps
(`pre-doa-backup`): 136 message events, 87 distinct stored IDs. No
proprietary bytes are quoted; offsets and rules only.

## Where they live

Each map's `.msb` holds events in ascending type order. Type 6 is the
developer-placed orange ground message (event names: `魔法血文字N`
"blood writing", `チュートリアルメッセージNN` "tutorial message",
`ヒント` hints, arena explanations). Three maps have none
(`m11_00_00_00`, `m13_02_00_00`, `m18_00_00_00`).

## Event layout

The 28-byte event header is shared with all events: name offset 28,
then the shift_jis name, a 16-byte `ahead` struct and the `bhead`
data. For type 6, `bhead` owns 2 ints:

```
[textId+131072, unknown01]
```

- `textId+131072`: the message text. Subtract 131072 (`0x20000`) to
  get the `Blood_writing_.fmg` entry ID in `menu.msgbnd.dcx`. Verified
  for all 87 distinct stored IDs (e.g. 132072 → 1000 'Path ahead',
  140072 → 9000 'Move'). Fixed dev texts live below ID 10000;
  10000+ are soapstone templates needing word parameters the event
  cannot supply, 30000+/1000000+ are single words.
- `unknown01`: 0 or 1. Reads 1 for 105 of 136 events: every message
  without an area reads 0, and all but five messages with an area
  read 1 (exceptions: `m13_00_00_00` seq 0/4, `m13_01_00_00` seq 0,
  `m17_00_00_00` seq 1/2). Meaning unproven; the editor preserves
  it and never edits it.

What reads as six more `bhead` ints (`28, nextPart, nextType,
ordinal, aheadOff, bheadOff`) is not stored per event: it is the
follower's header seen through the overlap (see The event chain).
`28` is the follower's name offset, `nextPart`/`nextType` its part
and type, `ordinal` its seq, `aheadOff`/`bheadOff` its own
ahead/bhead offsets. Verified byte-identical for all 2120 chained
events in all 17 maps. The "1-based ordinal ending in 0" is the
follower seqs read positionally: message seqs run 0-based with no
gaps, and every message run is followed by a type-7 event at seq
0.

The `ahead` struct is `[area, point, flag, 0]`:

- `area`: index of a type-5 part, or -1. Every used value points at
  a type-5 part (names `hNNNNB0`); tutorial, hint and arena messages
  mostly use -1. What the zone changes is unproven.
- `point`: index of the event's position point, or -1, which hides
  the message (the Battle of Stoicism spares use this).
- `flag`: an event flag ID, or -1 for always shown. The starting-
  class gear tutorials carry consecutive flags 1813200-1813204 and
  1813210/1813220-1813221, all referenced by `m18_01_00_00.emevd`,
  so the flag almost certainly gates the message; exact flag
  meanings are unmapped.
- Fourth int is 0 in all 136 events.

`part` (header) is a map-piece (type 0) or object (type 1) part the
message anchors to. Part 0 is a map piece in every map. Message
events sharing one point sit on the same spot (the class-gated
variants do this deliberately).

## The event chain

Events pack so each chained event's data ends where its follower's
header begins: the six tail ints overlap the follower's first six
header ints byte for byte. Owned data ints per type: type 0 and 2
use 1, types 1 and 6 use 2, types 7-10 use 4. Types 3, 4, 5, 11
(and the lone type 12) carry self-sized `bhead` data instead
(measured: 64, 52, 256 and 32 bytes) and overlap nothing. Verified
for every event in all 17 maps: all 2120 chained tails match
their follower headers exactly, no file ends on a chained event,
and every event directory runs in ascending file order.

Because the tail *is* the follower's header, stitching writes
nothing: filing the bytes in order links them, and "writing" a
tail would overwrite the follower's part, type, seq and offsets.
The editor therefore inserts and removes message bytes
physically (see the API section), never by patching tails.

Maintenance rules for edits (all verified against vanilla):

- Splice a new type-6 event's owned bytes (header, name, `ahead`,
  two data ints) ahead of the first event with a type above 6
  (message runs sit between the type-4 and type-7 runs), and file
  its directory entry at the same position. The predecessor's tail
  re-seats onto the new header by itself.
- New `seq` is max message seq + 1 (0 when the map has none). Seqs
  stay stable: removing a message leaves its neighbours' seqs (and
  the ordinals read through them) alone.
- Excise a removed message's whole span (up to its follower's
  base) after dropping its directory entry, so the predecessor's
  tail re-seats onto the follower. Refuse a message filing last:
  with no follower base there is no span to cut.
- New points take `words[2]` equal to their directory position
  (true for all 3755 points); new names are shift_jis like every
  MSB string.

## Editor API (`plugins/ds1/msb.py`)

Identity is `('message', seq)`; list entries also carry a display
`key` of the form `message:<seq>`, mirroring the light entries.
`messages()` returns one entry per message sorted by seq: key,
type, seq, name, pos (None when hidden), point, pointName, part,
partName, area, areaName, flag, textId, storedId and sharers (other
events standing on the same marker).

`read_message(key)` returns the detail row: key, kind, textId,
name, point, part, areaPart and fields. The fields are text
(Blood-writing entry ID), point (this map's markers plus -1 for
hidden) and flag, with posX/posY/posZ only while the message has a
marker. The position fields name their sharers: the write lands on
the shared point, so every event on it moves along.

`edit_message(key, field, value)` rewrites one field in place and
returns the row. Text must be a storable non-negative int, flag a
whole int, point one of this map's markers or -1; position edits
need a marker and a finite number. `message_modified(key)` reports
session edits; `dirty_count` counts them.

`add_message(key)` duplicates a message onto its source's spot
with a fresh seq (max + 1) and a fresh name. The copy's owned
bytes splice in ahead of the first event above type 6, in the
list *and* the directory, so reload order, tails and ordinals
survive the round trip with no tail writes at all.

`create_message(text_id, pos, name=None)` builds one from
scratch: a fresh marker under it, anchored to the map's first map
piece or object, carrying the first message's area (-1 when the
map has none), no flag, and unknown 0. It fails before the marker
lands when the map files nothing after messages.

`remove_message(key)` excises the message's whole span after
dropping its directory entry, so the neighbours re-seat across
the gap; the marker stays for its remaining sharers. It refuses
a message filing last, where no follower base bounds the cut. It
returns `{'type', 'id', 'name'}` and records
`{'type', 'id', 'name', 'kind'}` in `removed`, the shape the
changes list reads.

`export()` returns the file bytes. A splice or excision slides
later bytes along and shifts every absolute offset after it:
cached entry bases and spans, all four directories' name, entry
and link offsets. Entry-internal pointers are relative and need
nothing. The vanilla shadow takes the same cut (zeros for added
bytes), so survivors keep comparable originals and edit-then-
revert still restores the session's bytes. New markers and
placement copies append at the end and rewrite their parameter
directory there, dragging later directories along.
`merge_units()` covers text, point, flag and the spot, so plain
edits field-merge; adds and removes change the length and merge
whole. A no-op export is byte-identical.

## Unknowns

- `bhead[1]` (see above).
- Type-5 part and `area` semantics (zone records? volumes?).
- What the `part` anchor changes (culling? streaming?).
- Event-flag ID meanings beyond the class-tutorial pattern.
