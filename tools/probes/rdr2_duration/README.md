# Duration category experiment (#151)

This is an experiment, not a gameplay change. It does not assume that category names are durations. Use a disposable save. Do not overwrite a normal save. The persistence comparison uses a separate manual test slot only. Restore the catalog and remove the probe before normal play.

## Ready local controls

The prepared local bundle is `C:/Users/Lexer/AppData/Local/Lexeditor/probes/duration-151`.

1. Close RDR2, then open **Activate.cmd** in that folder. It uses the built probe. It moves the four reviewed ASIs aside and installs the prepared catalog and probe in one operation. If any step fails, it restores completed steps. Keep any reported recovery path if restoration fails.
2. Run the test below after activation succeeds.
3. Close RDR2 and open **Restore.cmd** in the same folder. It restores the exact catalog and ASIs. A changed file stops restoration of that file; the recovery bundle remains available. Repeated Restore is safe. Repeated Activate is refused until restoration is complete.

No build or command assembly is required. These helpers do not start the game or change save files. The single catalog bundle uses about 103 MB. Installation temporarily needs another 52 MB. Do not delete the bundle before restoration succeeds.

The installed GameplayTweaks core/tonic logic can invalidate measurements. Isolation moves GameplayTweaks, Rampage, Banking and CollectibleCalibrator into the bundle while preserving vfs.asi for LML. Unreviewed additional ASIs stop activation. Two log files are retained beside the probe; preserve needed logs before more launches.

## Controls

The initial case is 1. F8 moves to the next case while sampling is stopped; the log records its item name. F9 grants one selected item only when fewer than two are owned. F10 starts or stops sampling. Keys work only while the game has focus. The probe never sets core values, attribute points or ranks.

Start sampling before consuming the selected tonic in the satchel. Inventory count drop marks actual consumption; the key press is not treated as consumption. Sampling stops after ten minutes. Each launch keeps one current CSV and one previous CSV beside the ASI, with at most 4096 rows in the current file. Copy relevant evidence before another launch.

## Test matrix

All amounts are zero; the behavior supplies overpower. Time and timeunits below are raw data values, not claimed seconds.

| Case | Existing item label family | Behavior | Time | Units | Category |
|---|---|---|---|---|---|
| 1 | Health Cure | Health overpower | 3 | 2 | 1 |
| 2 | Potent Health Cure | Health overpower | 3 | 2 | 2 |
| 3 | Special Health Cure | Health overpower | 3 | 2 | 3 |
| 4 | Miracle Tonic | Health overpower | 3 | 2 | 4 |
| 5 | Potent Miracle Tonic | Health overpower | 9 | 2 | 1 |
| 6 | Special Miracle Tonic | Health overpower | 3 | 1 | 1 |
| 7 | Snake Oil | Stamina overpower | 3 | 2 | 1 |
| 8 | Potent Snake Oil | Health overpower | 9 | 2 | 4 |

For each case, load the same clean baseline, start the trace, consume once and record visible gold start/end, radial tier and count decrease. Do not take damage or consume another item in the first comparison. Compare cases 1–4 to isolate category; 1/5 and 1/6 isolate time and timeunits; 1/7 compares behavior.

For stacking, repeat case 1 then case 4 at a recorded interval, then reverse their order from a clean baseline. Record whether the second item replaces, extends or leaves the first effect. For persistence, use a separate disposable save and report whether the visible state and readbacks survive reload. No expected outcome is asserted before observation. Report missing effects, wrong item consumption, absent count drops, crashes and all CSV files used.

For the save/load comparison, start from an existing safe manual save, keep its slot unchanged, and save the experiment to a distinct unused manual slot. Record that slot before saving. Reload only that test slot for the persistence measurement. After file restoration, return to the untouched baseline slot. Do not delete or change any save as part of these tools.
