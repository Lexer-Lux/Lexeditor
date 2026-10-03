# World encounter selection

Verified read-only against the supported English Steam executable, SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`.
Run `python tests/ff8/verify_ff8_world_encounter_selection.py` with that
executable installed. The check executes original instructions and original
tables in Unicorn; it neither starts the game nor modifies installed files.

## Eight slots, each independently replaceable

The normal encounter groups are eight little-endian scene IDs in `wmsetus.obj`
section 4. `world_map.py` reads and edits those IDs. The native selector at
`0x541E98` indexes the group as `group * 8 + slot`, without requiring repeated
IDs. All eight IDs can differ. The alternative group source at `0x541E80`
uses the same slot selection, with a group-index adjustment.

Region and ground rules choose a group. They do not give each group its own
slot-weight table. A formation repeated in several slots gets the combined
initial-selection chance of those slots, not the number of copies divided by
eight. Replacing one occurrence changes only that slot; editing the formation
itself changes it wherever that formation is used.

## The weight table and the comparison are separate facts

The global executable table at `0xC75F10` contains
`37, 37, 37, 37, 36, 36, 24, 12`. Starting at `0x541E4B`, the selector compares
the random byte with each table entry, subtracting an entry and advancing only
when the byte is **greater than** that entry. Zero is a possible random byte.
Consequently, the first slot accepts 0 through 37 inclusive; the last slot has
only eleven remaining byte values.

| Slot | Initial outcomes out of 256 | Initial chance |
| --- | ---: | ---: |
| 1 | 38 | 14.84375% |
| 2–4, each | 37 | 14.453125% |
| 5–6, each | 36 | 14.0625% |
| 7 | 24 | 9.375% |
| 8 | 11 | 4.296875% |

These counts assume a uniform random byte, equivalently a uniform distribution
over all 65,536 counter/shift states. The native check exhausts that state
space. They are not a promise about the frequency in a particular play session.

The random table at `0xC75D20` is a permutation of all 256 byte values. The
formation counter at `0x2040A62` advances before reading the table. At counter
wrap, the shift at `0x2040A61` increases by 13; the shift is subtracted with
byte wrap. Exhausting only the 256 counters at one fixed initial shift can
give different totals and does not prove uniform-byte probabilities.

The [FF8 speedrunning encounter tool](https://github.com/ff8-speedruns/world-map-encounters)
uses the table entries themselves as weights out of 256. That agrees for the
middle six slots, but differs by one outcome for the first and last slots of
this supported executable. Native execution is the evidence for the counts
above; the tool is not evidence for the executable's comparison boundary.

## The previous battle changes the final result

At `0x541EAE`, the selected scene ID is compared with the previous scene at
`0x20400A0`. A match causes one more draw from the next random-table state.
The second result is accepted even if it repeats again. This compares scene
IDs, not slot numbers, so repeated IDs in different slots still trigger it.

The initial percentages above therefore do not describe the final conditional
chance when the previous scene is present in the group. The draws use
consecutive states of the deterministic table, so an independent-draw formula
is not established by this check. The check verifies mixed groups against
separate native first and second draws, plus all-repeated groups across counter
wrap, for both group sources.

## What an editor can change

The group's game data contains scene IDs, not eight editable chance values.
Moving or repeating a scene among slots changes its initial chance using the
global weights. A different weight table or retry rule changes executable
behavior and requires a Hext patch in an explicitly created mod. It is not a
plain `wmsetus.obj` probability edit.
