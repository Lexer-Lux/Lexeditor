# GitHub #181 - vignette removal

## Recurrence audit before implementation

- Prior failure class: the old generator changed only weather presets and explicitly skipped every `timecycle_mods_*.xml` modifier library. That can pass a weather-file check while local, directional, and light-driven modifiers still restore the vignette.
- Primary evidence: `_downloads/make_novignette.py` contains the skip; `_downloads/extract/update_1_common/common/data/timecycle/timecycle_mods_1.xml` contains many non-zero `postfx_vignette_intensity` values, including location and camp modifiers.
- Reference evidence: current public vignette-removal packages describe modifying all files under `update_1.rpf/common/data/timecycle`, not weather files only. An older weather-only package also has a user report of an angle-dependent brightness return.
- Sanctioned path: replace Rockstar's native timecycle XML through LML. Do not add a per-frame post-processing native fight.
- Execution proof required: every source XML that contains `postfx_vignette_intensity` must have a corresponding installed replacement; every replacement must preserve all other XML and set only that field to zero.
- Player-visible boundary: rotate through a full circle at the Valentine stables, face the stable from several positions, and toggle the lantern. The vignette must not return. Static XML checks cannot prove the rendered result.

## Repair

- Removed the generator's `timecycle_mods_*.xml` exclusion.
- Generated replacements for 61 source files and zeroed 299 vignette-intensity fields. This added the previously omitted `timecycle_mods_1.xml` and `timecycle_mods_3.xml` libraries.
- Added both modifier libraries to `MyOverhaul/install.xml`.
- `verify_vignette_removal_issue_181.py` proved that every source vignette field has one replacement, every value is zero, and no other XML field changed.
- The game `lml/MyOverhaul` directory is a junction to the workspace. The installed modifier file and source file hashes matched, so the new data is live for the next game launch.
