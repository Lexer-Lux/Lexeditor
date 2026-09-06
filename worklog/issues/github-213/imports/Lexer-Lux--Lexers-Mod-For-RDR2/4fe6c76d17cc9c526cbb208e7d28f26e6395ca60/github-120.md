# GitHub #120 - Collectible icons outside the southwest map

## Diagnosis and correction - 2026-08-06

The live 2560x1440 screenshot showed mixed collectible icons in the diagonal
blank wedge between New Austin and West Elizabeth. This was not a card-only
regression: the visible set included bone, POI, shack, and treasure glyphs.

The original conversion applied one global affine Y transform to the public
map projection. The 144 cigarette-card rows now have independent, keyed game-
space positions, and comparing them to both archived source maps proved the
southern projection was compressed northward. Errors at the southern edge
reached roughly 1.7 km while X remained aligned. That compression placed eleven
non-card rows inside the exact blank wedge visible in the report.

`fix_collectible_south_projection_120.py` uses the 144 authoritative card Y
positions as control points. Shackmaps-backed rows use piecewise-linear
latitude interpolation; the two MapGenie POIs use a separate quartic least-
squares fit against MapGenie's own 144 card pins, avoiding the old unstable
cross-site extrapolation. The repair is spatially scoped to the reported blank
wedge and changes only Y for these eleven rows:

- five Dinosaur Bones: 9, 10, 28, 29, and 30;
- two POIs: Flying Machine and Sperm Whale Bones;
- three shacks: Pleasance House, Silent Stead, and Swadbass Point;
- The Elemental Trail Map 3.

All category, name, X, requirement, and card fields were preserved, as were all
coordinates outside that set. Pre-existing concurrent gang-hideout rows were
also preserved. Running the fixer again reports zero changes.

## Static acceptance

`python tools/reverse-engineering/verify_collectible_projection_issue_120.py`
passes: all eleven corrected Y values match the calibrated output, no non-card
row remains in the screenshot-defined blank wedge, all 144 keyed card controls
remain, and the normalized hash of every unrelated field and coordinate is
unchanged.

Runtime acceptance remains required: open the full map and confirm the former
southwest floating cluster is gone, then spot-check at least one corrected bone,
POI, shack, and The Elemental Trail Map 3 against its physical location.

## Authoritative rebuild replacing outlier edits

The eleven-row screenshot repair was not sufficient. The new deterministic
rebuild replaces all 30 dinosaur bones, all 20 dreamcatchers, and 200
orchid/alligator-egg exotic pins with RDOMap's game-derived authored positions
through its checked-in exact map/game converter. All 250 are verified against
the source and a second rebuild changes zero rows.

POI, shack, legendary-fish, grave, plume and treasure pins still lack an
equivalent complete authored game-coordinate source. This issue therefore
remains `actionable`; the partial correction does not justify `test me`.

## Complete coordinate rebuild after failed runtime test

The runtime screenshot after the 268-row rebuild proved the remaining 166
scraped rows were still wrong. The conspicuous west-of-map points were the
categories the rebuild had left on the old projection: POIs, shacks, treasure
clues, legendary fish, and plume locations. For example, the Jesuit Missionary
POI still had Y -1871.305 even though its far-west position belongs at the
southern edge; Riley's Charge, Two Crows, and Donkey Lady were similarly about
1.3 km too far north.

The rebuild now covers every non-card, non-hideout CSV row:

- 268 bones, dreamcatchers, carvings, graves, orchids, and alligator-egg pins
  retain RDOMap's game-derived coordinates;
- 109 Shackmaps fish/shack/treasure/plume pins use a longitude-linear and
  latitude-quintic transform derived from 192 exact controls: all 144
  game-sourced cigarette cards plus 30 bones, 10 carvings, and 8 graves;
- 57 MapGenie POIs use a separate transform derived from that site's own 144
  card pins, rather than passing through the incompatible Shackmaps projection.

This changed all 166 formerly uncorrected rows. The obvious failures now move
to the correct southern band: Jesuit Missionary Y -3663.521, Sperm Whale Bones
Y -3571.831, Riley's Charge Y -3167.116, Two Crows Y -3021.016, and Donkey Lady
Y -2984.935. A second rebuild changed zero rows.

`verify_collectible_projection_issue_120.py` independently reconstructs both
calibrations and checks all 268 exact plus 166 calibrated pins. It passes.

The corrected CSV is built locally but is not installed while RDR2 is running.
The issue remains `actionable` until installation; only then does the full-map
runtime check become a real `test me` item.
