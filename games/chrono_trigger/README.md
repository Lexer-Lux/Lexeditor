# Chrono Trigger Steam — fresh replacement

This plugin deliberately replaces the rejected #454 architecture. The old code is historical evidence only; it is not the implementation base.

## Current useful path

The replacement targets the Steam release (`613830`) and keeps `resources.bin` immutable:

1. read and validate the ARC1 resource archive;
2. edit keyed `Localize/<lang>/msg/*.txt` records;
3. edit existing fixed-size PC area exits (`MapJump*`);
4. edit existing fixed-size PC treasure records (`Takara*`), preserving alias sentinels and the unmodelled trailing word;
5. save only changed resources to an external project;
6. export a deterministic `.ctp` ZIP whose members use the original `resources.bin` paths.

No generic raw-file editor is counted as format integration. The Data Map keeps other recognized Steam families visible as not integrated.

## Deployment boundary

The project does not rewrite `resources.bin`. `.ctp` is the established Chrono Trigger patch shape: a normal ZIP containing replacement resources at archive-relative paths. CTExt is a known Steam loader for loose files/CTP packages, but its upstream repository currently has no clear top-level redistribution license, so this replacement neither copies nor bundles it. Export is tested; real-game loading remains a separate acceptance step.

## Safety

- Installed `resources.bin` is read-only.
- Writes are stale-hash guarded and atomic inside the selected project.
- CTP export includes changed `Game/...` and `Localize/...` resources only.
- Unknown exit flag bits and the final unknown treasure word are preserved.
- Exit/treasure record counts are not resized.
- Treasure alias sentinels (`x=0,y=0`) are preserved read-only rather than rewritten into guessed records.
