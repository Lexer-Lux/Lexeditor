# Chrono Trigger research sources and licenses

No third-party source is vendored by this plugin. The implementation is a small independent Python implementation of publicly demonstrated Steam layouts.

## CTViewer

Source: https://github.com/GitExl/CTViewer

Revision audited: `2e5a206e09f0028fd5a1ca6cb9a9ed18bfc64fea` (2026-07-19).

Used as the primary current-PC reference for `resources.bin`, scene exits, treasure records, current-PC scene/world families and the explicit separation between PC and SNES layouts.

License (MIT), copyright 2025 Dennis Meuwissen. The complete upstream license is available at `LICENSE.txt` in CTViewer.

## ct_nx

Source: https://github.com/NaGaa95/ct_nx

Revision audited: `e6bc0b4b032df2dbc62a6f142fe08ae0470b61fe` (2026-07-08).

Used as an independent MIT-licensed corroborating reference for the Steam/Android ARC1 layout and ChronoMod-compatible `.ctp` semantics: standard ZIP members whose paths match `resources.bin` resource paths, applied without changing the original archive.

License: MIT. Copyright (C) 2021 Andy Nguyen, fgsfds. The complete upstream license is in ct_nx `LICENSE`.

## Evidence-only references (no code copied or bundled)

- jimzrt / ChronoMod — `4566e9dea7a3510cbb442991cd9efa223b95fdc7` (2025-07-11), historical `resources.bin` tooling. No clear top-level repository license was found during this audit, so its code is not reused.
- TheRealBiggs / CTExt — `892c47166c56f6d20a2c805c303586096e8d466a` (2026-07-04), Steam loose-file / CTP runtime behavior. No clear top-level repository license was found during this audit, so it is not bundled or copied.
- OnemusCT / Temporal Redux — `d8d4e38c0bf08b51a29441ef7ea2a489d63da58f` (2026-09-02), GPLv3 event-editor research. It is not copied into this replacement; event editing remains outside the first low-cost slice.
- julianxhokaxhiu / CTNx — `fda83d565897737d9853cb5ba0b4e7e5d87aa674` (2024-11-14), GPLv3 reimplementation research. It is edition-adjacent evidence only and is not used to transfer SNES/DS layouts into Steam.
