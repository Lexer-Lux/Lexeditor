# Dark Souls Remastered mod loading

## Scope and acceptance

This work replaces the single-archive deployment model with a pre-launch
compositor and the existing ModEngine2 Dark Souls Remastered runtime fork.
It does not target Prepare to Die Edition. The existing Apply/Disable path is
legacy file replacement, not a multi-mod loader; it remains available for
recovery until the replacement has passed the acceptance gates below.

The closest existing Lexeditor model is the FF8 pre-launch compositor: combine
vanilla-relative changes before handing an isolated output to an established
runtime. Reuse DS1's audited BND3/DCX/PARAM reader and DS3's field definitions;
do not introduce another archive parser or a plugin-specific UI framework.

### Runtime source selection

- Selected source: https://github.com/AltimorTASDK/ModEngine2/tree/76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d
  (`feat/dark-souls-remastered`, commit `76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d`).
  Its `LICENSE-MIT` permits reuse with the required notice. This is a source
  pin, not a tested binary pin or a claim about every transitive dependency.
- `installer/dist/launchmod_darksoulsremastered.bat` selects `-t dsr`.
  `launcher/launcher.cpp` identifies Steam app 570940 and
  `DarkSoulsRemastered.exe`.
- `src/modengine/ext/mod_loader/mod_loader_extension.cpp` installs a
  `CreateFileW` hook. `archive_file_overrides.cpp::find_override_file` returns
  the first existing file in the configured roots. Put the generated merged
  overlay first, not last. This runtime does not merge PARAM records.
- Upstream https://github.com/soulsmods/ModEngine2 is archived and its README
  does not claim released DSR support. Its multiple-root example only supports
  non-conflicting files. Do not bundle upstream and label it DSR-capable.
- https://github.com/garyttierney/me3 does not currently list DSR among its
  supported games. It is not a drop-in substitute for this target.
- The Nexus DSR ModEngine2 repack (mod 790) corroborates an existing DSR use
  case, but is not the source of redistribution rights or a verified binary.

### Required behavior

1. Inputs remain separate, read-only mod folders. The caller supplies a common
   vanilla baseline and its expected hash. A matching hash proves consistency,
   not that an already-modified installation was originally vanilla.
2. Only changes relative to that baseline participate in composition. A mod's
   unchanged vanilla values must never undo another mod's changes.
3. Audited PARAM fields compose by table, row ID and field, including packed
   bitfields. A whole numeric field is indivisible: do not splice its changed
   bytes into a third value neither author requested.
4. Conflicts are reported with both contributors. Default is refusal; explicit
   load-order resolution may select the later/higher-priority contributor.
   Unknown members use whole-member conflicts, not speculative field merges.
5. Disabled mods do not contribute. Dependencies must be enabled and ordered
   before their dependents. Missing dependencies and cycles are errors.
6. Build a separate overlay/config snapshot without modifying the installation,
   source mods, executable, existing loader configuration or legacy backup.
   Refuse unsafe paths, changed inputs and unsupported structural edits.
7. Restore the old replacement deployment explicitly before validating the
   runtime path. Do not silently label the old installed mod as vanilla.

### Release gates (not completed)

- [ ] Field/member composition and deterministic conflict regression tests.
- [ ] Isolated data-folder staging and ModEngine2 configuration tests.
- [ ] Bundle a pinned DSR-capable runtime and all required license notices.
- [ ] Fix and test upstream's manual-path bug: its `-p` branch always uses
      `parent_path().parent_path()`, which is wrong for the root-level DSR exe.
      Also make process-creation failure return a nonzero exit status.
- [ ] Audit transitive dependencies; exclude proprietary debug font/PARAM
      assets rather than indiscriminately copying the upstream installer tree.
- [ ] First-time helper setup and shared Updates drawer, with no auto-updates.
- [ ] Shared mod-list/import/enable/order/remove UI and host launch integration.
- [ ] Rendered UI inspection, distinct from source and API checks.
- [ ] Real publicly distributed mods tested alone and in overlapping profiles.
- [ ] Installed-game launch, observed combined changes, disabling/removal and
      unchanged base-game hashes verified on a supported DSR executable.

No source pin, config file, parser test or synthetic fixture satisfies the
runtime, real-mod compatibility or installed-game acceptance gates by itself.
