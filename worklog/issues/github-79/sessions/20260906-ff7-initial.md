# #79 — FF7 dataset integration

Branch: `fix/ff7-data-and-tweaks-20260906`.
Base commit: `60eda056e233148debf6ef660bf19611ecf76518`.

Implemented: nine-slot Characters editor (21 starting numeric fields and five
limit-learning thresholds), per-category availability, concrete unresolved
cards, independent auxiliary-page loading, validated project saves with backups
and snapshot checks. Shared FF7 code covers both product-relative paths.
No FF8 files or shared runtime/UI implementation changed.

## Verification performed

- `python tools/verify_ff7_datasets.py`: 19 tests passed. Includes all 234
  character-field/slot combinations, byte-preservation/readback, both product
  paths, missing/truncated/corrupt data, category isolation, invalid writes,
  stale clients, backup preservation, installed-source protection, and HTTP.
- `python tools/verify_ff7_ui.py`: four Chromium tests passed, including both
  editions' character editing/saving, invalid input, read-only restoration,
  independent failed requests and FFNx refresh races.
- JavaScript syntax checked with Node; Python modules compile.

Fixtures contain no game assets. Audio and OS process discovery are doubles.
Browser tests execute the production page and HTTP API with a shared-component
facade and an offline fetch bridge; they do NOT establish shared-component
rendering, actual Windows process detection or game acceptance. No installed
FF7 kernel/executable or Windows host was available. Existing installed-product
smoke commands were not run. New FF7-only CI repeats these asset-free checks.

Exact unmodified local test dependencies matched Git blob IDs:
`kernel.py` f0c6518171ed8da2663344b7806dce7b08028f32;
`paths.py` 5ba997435c28657e5b4797978cbb6187458bc90f;
`platform_config.py` 882b1b08ff91551eb96cc5d8a64a265d22ac94de.

## Remaining

Review/merge the isolated PR; verify actual installed English kernels and the
real shared UI on Windows. Enemies, encounters, shops, full growth/equipment/AI
editing and kernel2 text remain unimplemented, not disguised as editable.
Keep the issue open pending acceptance; do not claim every FF7 format is done.

## Player checks (after obtaining the branch in a separate checkout)

- [ ] Open each installed FF7 edition; Characters must show nine named slots,
      starting stats and limit-learning fields, without hiding existing tabs.
- [ ] In a disposable mod project, change the first character's Strength by 1;
      save, close/reopen and confirm it persists. Restore the original value.
- [ ] Select Vanilla and confirm fields/restoration cannot modify it. Check
      the installed kernel was not overwritten by the project save.
- [ ] Open Enemies, Encounters, Shops and Data Map; each must explain its own
      remaining work. Report blank tabs, wrong names or save errors with the
      edition, field and a screenshot. Do not test starting stats in an old save.
