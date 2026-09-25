# World-map sky and fog zones

Settled facts behind the World page's Sky Colours subtab. Sources: the FF8
modding wiki's wmset reference (credited in the plugin's Credits under
`ff8`), and this repository's reading of the shipped file. Checked
2026-09-25.

## The record

`wmsetus.obj` section 32 holds an offset list ending in a zero sentinel, then
84-byte records: three signed 32-bit words, five `RGB+pad` colours and nine
16-bit atmosphere values.

| Offset | Field | Meaning |
| --- | --- | --- |
| 0 | `x` | World coordinate |
| 4 | `y` (second coordinate) | World coordinate |
| 8 | `transition_range` | Fade distance |
| 12, 16 | `light_color_1`, `light_color_2` | Light colours |
| 20, 24, 28 | `fog_color_1..3` | Fog colours |
| 32 | `atmosphere[0..8]` | Nine 16-bit parameters |

The wiki calls the record "per-zone lighting and atmospheric parameters" and
names the third word a **fade range**, which is what a distance rather than a
coordinate would be.

## Which word is the range, in the shipped file

The plugin read the three words as `x`, `z`, `y` following OpenVIII's Vector3
order, and the Sky Colours page therefore showed the third word as a "Y
coordinate". The shipped records say otherwise:

| Word | Distinct values in 8 records |
| --- | --- |
| first | 8, all different |
| second | 8, all different |
| third | 4: 0, 16384, 24576, 40960 - all multiples of 8192, and five records share 16384 |

A coordinate that only ever takes four round values is not a coordinate; a fade
distance chosen in round numbers is exactly that. So the first two words are the
zone's position and the third is its fade distance, as the wiki has it. The
editor presents them as X, Z and RANGE; the stored order is unchanged, so saving
is unaffected.

## What is not established

- **How the game picks and blends zones.** The fade distance says the colours
  change gradually rather than snapping to the nearest record, but whether the
  runtime takes the nearest zone, fades between two, or weights several is not
  proved by any source read here. OpenVIII has no sky module in its tree and the
  FF8 decompilation names no sky or fog symbols, so this is a gap, not a
  settled fact.
- **Where the zones sit on the map image.** Answered since this page was
  written: the world-to-map projection was calibrated and its evidence is in
  [world-terrain.md](world-terrain.md) (column = x/2048 + 64, row = z/2048 + 48
  on the 128 by 96 grid). The Map page draws each zone as a marker from it, and
  the fit is a calibration, not a proved origin - which is why the sky panel
  says so when a record is moved by hand.
