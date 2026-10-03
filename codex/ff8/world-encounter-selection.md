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

## An in-place per-group selector

`encounter_chances.selector_patch` authors a replacement for exactly
`0x541E2D..0x541EDF`, the existing 178-byte selection/retry block. It rejoins
the original function at `0x541EDF`. No code cave, driver callback, or new
allocation is needed by this block. The executable hash gates emission.

The replacement reads a caller-supplied extension relative to the normal
encounter-group pointer at `0x2036BE8`. The extension starts with one default
record, then one record per normal group. Each record has eight unsigned
16-bit outcome counts totalling 256. A group can assign zero to a slot or all
256 outcomes to one slot. Alternative groups retain the leading default
distribution. The builder validates every outcome record before encoding it.

`verify_ff8_encounter_chance_patch.py` compares separate original and modified
emulators across all 65,536 initial counter/shift states using the default
distribution. It also verifies native retry parity, frame/register preservation
at the rejoin, zero and 256 outcomes, isolation between normal groups, the
alternative-group fallback, and the two-draw bound when a previous formation
has a 100% chance. The weight extension is an authored memory fixture in this
check; this evidence does not establish loading a larger game data file or
deploying a mod in the running game.

## Appended weight storage and native loading

The weight extension follows the original `wmsetus.obj` bytes, with one zero
padding byte only if the original length is odd. It does not move sections or
change any original byte. The records are the leading vanilla distribution
and one distribution per normal group, as described above. A 48-byte footer
uses `<8sII32s`: magic `LEXCHN01`, original file length, group count and the
SHA-256 digest of the weight records. The reader rejects invalid bounds,
counts, checksums, distributions and a modified alternative-group fallback.
Updating the extension replaces it rather than appending another copy;
restoring all defaults returns the exact original file.

The original world-load table names `dat\\wmsetus.obj;1` with destination
`0x1E9DC3C`. The file helper `0x52D400` seeks to EOF, reads that complete size
into the destination, then closes the file. Section setup `0x542DA0` adds
the fixed header offsets to that destination. Weight output is capped at
1 MiB, before the next known world-data address `0x1F9DC40`; oversized
extensions reject before publication.

`verify_ff8_encounter_weight_storage.py` executes both original native helpers
with archive open/seek/read/close emulated. It reads the installed vanilla file
without changing it. For the surveyed 84-group file, the original load is
1,016,368 bytes and the extended load is 1,017,776 bytes. The check proves
complete reads, untouched bytes beyond each read, identical section-setup
state, and actual selection from the loaded extension for the first and last
normal groups across all random shifts. The unmodified game-data parser also
returns exactly the same original records. This establishes the native loading
path in emulation, separately from deployment and running-game acceptance.

## Saving a weight/data pair

The world-map API exposes `initialOutcomes` on each group. A group Save can
provide that complete eight-value distribution with its eight scene IDs.
Changing a distribution requires the SHA-256 of the loaded world source;
a stale or absent hash rejects before publication. The generated Hext must
match the existing weight extension exactly before either is updated. An
unsupported executable or externally modified generated patch rejects.

The shared FF8 project-file publisher stages the complete world result and
the generated Hext before replacing either. Combined rail, texture, geometry
and ground-name outputs join the same batch. Prepared source bytes and output
snapshots guard publication. Failed publication restores only files still
holding the bytes installed by this operation, including their timestamps;
failed restoration retains one recovery set and blocks later World saves.
Restoring every default removes the trailer and leaves the generated Hext
empty. Card saves use the same publisher with their existing recovery folder
and restoration callback.

`test_ff8_encounter_chance_save.py` uses the production HTTP handler with
authored world-data and executable-signature fixtures. It covers Save/read,
separate-group updates, exact default restoration, malformed/stale requests,
first/second staging and publication failures with new and existing files,
retries, retained failed-restore originals, external edits, unsupported
executables and combined ground-name publication. The selector's actual
supported-executable behavior is established separately by the native checks.
