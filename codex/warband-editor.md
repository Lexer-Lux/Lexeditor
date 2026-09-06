# Warband editor boundaries

## Selected modules and launches

The host delegates process operations only when a plugin registers
`GamePlugin.game_process_factory`. Other games keep the existing launch path.
The selected project is passed from ProjectManager at launch time, not from a
module-import-time default environment variable.

Warband's compiled module root is the selected directory when it contains
`module.ini`; otherwise it is `<project>/Module`. An installed directory in
`<game>/Modules` must resolve to that same root. Matching preserves the installed
alias name of a junction/symlink. No name-only fallback launches another mod.

When installed, `mb_warband_wse2.exe` uses
`--module <installed name> --no-intro`. The updater is never invoked. Without
WSE2, the installed stock `mb_warband.exe` is started without guessed flags.
Its owned launcher ComboBox is searched for exactly the selected installed
module. CB_SETCURSEL is followed by CBN_SELCHANGE and a selection readback;
only then is real Play control 1029 activated. Control 1040 is a decoy.
The adapter does not change the registry, game files, global keys or unrelated
windows. Missing/ambiguous choices fail rather than launch a different mod.
Both paths create their first process suspended, assign it to the owned Job
Object, and resume it, eliminating the Popen/child-handoff assignment race.

The Windows controller owns a Job Object, follows its member processes, and
requires a stable visible non-dialog game-sized window from the selected executable before reporting launch
success. A detected window is not proof that a campaign is playable. Stop applies
only to that owned job, not every process sharing an executable name.

Primary references:
- Stock launcher implementation: https://github.com/cuellius/warband-launcher-kit/blob/b7a81f8d3a9f8cedc009ca6a6074b2ac6009a5db/LoaderBase.cs
- Module selection notification: https://learn.microsoft.com/en-us/windows/win32/controls/cbn-selchange
- WSE2 author's launch syntax: https://forums.taleworlds.com/index.php?threads/warband-script-enhancer-2.384882/page-136
- Windows job process list: https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list
- Job information API: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject

## Coverage and source

Data Map `coverage` distinguishes `structured`, `view`, `source`, and
`unavailable`. Only the settings value editor is currently structured-editable.
Items/Troops/Troop Trees are read-only views; Python editing is source-only.
The legacy `status` field remains compatible with integrated/partial/not-integrated.
Missing Module System files must not prevent an installed module's UI from opening.

## Inventory rendering

A preview requires a loaded mesh, its loaded material, and a resolved diffuse DDS.
The cache identity includes the selected module path, mesh BRF fingerprint,
material BRF fingerprint, diffuse texture fingerprint, and reader fingerprint.
Fingerprints use path, size and nanosecond modification time, not full-file hashes.

`/api/item-icon?mesh=...` returns a generated PNG, HTTP 202 while queued, or an
explicit unavailable error. Icons use a fixed fitted three-quarter camera,
lighting and neutral ground. The renderer version and size also enter their key.
A foreground request promotes queued warm-up work. Icons are not WebGL canvases;
the separate full preview remains interactive. Assets stay in the installed game
and module; extracted geometry and generated images use the local cache.

## Troop trees

Connected upgrade components remain separate selectable trees. A component can
appear under every faction represented by its troops, preserving cross-faction
edges. Roots sit at the bottom. Strongly connected components prevent cycles from
hanging layout; cycle links and missing troop references remain visible. Selecting
a node updates the detail pane inside Troop Trees rather than navigating away.
