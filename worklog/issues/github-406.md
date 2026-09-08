# #406 — Add Final Fantasy VII Remake Intergrade plugin

## Current requirements

- Detect installed Steam/Epic FF7 Remake Intergrade.
- Integrate game DataObjects as structured shared-UI controls and expose Data Map.
- Preserve installed archives and unknown bytes; save to a project overlay only.
- Build and explicitly deploy a loadable mod PAK.
- Verify parser/write behavior without committing proprietary fixtures.

## Implementation state

Candidate implementation lives on `feature/ff7-remake-plugin`.

- `repak` v0.2.3 is a pinned installable helper.
- PAK indexes are scanned for paired `End/Content/GameContents/DataObject` assets.
- `.uasset`/`.uexp` pairs are extracted only when opened.
- The editor maps booleans, numeric values, floats, FNames and fixed arrays to
  typed controls. FStrings are deliberately read-only.
- Saves use source/project SHA-256 conflict checks, patch same-size fields only,
  write atomically under `<project>/content`, then binary-read back the result.
- Build creates `<project>/build/Lexeditor-FF7R_P.pak`; Deploy separately copies
  it to `End/Content/Paks/~mods`.
- Synthetic fixtures exercise parser, write, array, FName, malformed input and
  service save/readback without storing game binaries.

## Evidence / next work

Agent-side syntax and synthetic tests must pass, then CI on the candidate branch.
Live game acceptance remains separate: actual PAK indexing, representative
DataObject editing, game load, and deployed-value effect must be checked on an
installed copy before #406 is complete.
