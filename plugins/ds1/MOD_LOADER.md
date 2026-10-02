# Dark Souls Remastered mod-loader backend

## Delivery status

This is a draft backend, not a finished player-facing mod loader. The existing
Info/Apply action still calls `deployment.py` and replaces one installed archive.
Neither the new compositor nor profile exporter is connected to that action yet.
No Mod Engine executable or DLL is bundled, installed or launched by this change.

The target is Dark Souls Remastered PC/Steam, not Prepare to Die Edition. Synthetic
parser and profile tests do not establish compatibility with a retail build or
with any particular downloaded mod.

## Reused loader

The selected runtime source is
[AltimorTASDK/ModEngine2](https://github.com/AltimorTASDK/ModEngine2), branch
`feat/dark-souls-remastered`, pinned to
`76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d`. Its `LICENSE-MIT` permits reuse with
notices. Source references are also recorded in Credits.

This fork adds the `dsr` launcher target, Steam application 570940, and
`DarkSoulsRemastered.exe`. Do not silently substitute the stock Mod Engine 2
release: that is not the DSR-specific source reviewed here. The me3 project is a
potential future alternative, but its reviewed supported-games list did not
include DSR. Public availability of a different merger does not establish a
reusable license; no SoulMerge code or binaries are included.

`src/modengine/ext/mod_loader/archive_file_overrides.cpp` returns the FIRST matching
mod root. The profile exporter therefore places its composed overlay first and
then emits source mods in reverse priority order. Mod Engine redirects whole
files; `composition.py` handles the separate archive-composition problem.

### Required launcher correction

At the pinned revision, `launcher/launcher.cpp` converts the explicit `-p` game
executable into `.parent_path().parent_path()`. That assumption fits a game with a
`Game` subdirectory but not DSR's executable at the installation root. The
launcher-adjacent autodetection path has the same assumption. A bundled build must
correct and test both paths, including spaces and Unicode, before they are used.
No launcher patch or tested native build is supplied in this draft backend.

## Composition contract

`compose(base_bytes, [(mod_id, archive_bytes), ...], policy="error")` compares every
archive against the SAME caller-selected baseline, not against the preceding mod.
The list runs from lowest to highest priority.

- Different known fields or rows combine. Unchanged baseline values do not undo
  another mod. Identical overrides coalesce.
- A complete numeric field is one conflict unit, even when two edits happen to
  touch different bytes. Packed fields have separate masks, so neighboring flags
  can combine without damaging one another.
- A field whose physical layout is defined can be copied as authored even when
  the editor does not expose it. Padding remains protected. The compositor does
  not invent field meanings or values.
- Unmodeled binder members are indivisible replacements. Two different changes
  to one such member conflict, even if their byte offsets do not overlap.
- Row additions/deletions/reordering, relocated members, changed container or
  PARAM headers, row names and padding are rejected. This fixed-layout support
  is NOT universal Souls-mod compatibility.

The default rejects conflicts and returns their report through
`ConflictError.report`. The explicit `policy="last-wins"` option uses the higher
priority value and records the loser, winner, member, row and field. Values are
represented as bytes, with hashes instead of large opaque payloads. There is no
claim that conflict-free data changes are automatically gameplay-compatible.

The existing DS1 parser, metadata, field layouts and serializer are reused.
Unchanged output is byte-exact. Changed output is reparsed before it is returned.

## Isolated profiles

`mod_loader.prepare_profile(game_root, base_path, destination, mods,
expected_base_sha256=..., policy="error")` takes explicit `Mod` records. Each has
an ID, root, enabled flag, optional dependency IDs and optional baseline hash.
Dependencies must be enabled and already earlier in the specified order; this is
validation, not a version solver or an automatic dependency installer.

The caller must identify a known common baseline. Its SHA-256 establishes byte
identity, not that a previously modified installation is actually vanilla. A
mod's declared incompatible baseline is rejected. Undeclared baselines are
reported as unverified, not silently certified. An unchanged full archive cannot
express an intentional reset of a prior override back to vanilla; an explicit
patch format would be needed for that operation.

The destination must be a NEW folder outside the game and all source mods. The
export writes only:

- `merged/param/GameParam/GameParam.parambnd.dcx`;
- `profile.json`, containing source hashes, order, dependencies and conflicts;
- `config_darksoulsremastered.toml`, published last after the preceding files.

Other assets are referenced from their original mod roots, not copied into the
game. Different replacements of the same non-PARAM file require the same explicit
conflict decision. `ProfileConflictError.report` preserves those conflicts.
External DLL autoloading and the Scylla extension are not enabled by the exporter.
This is not an offline-mode or anti-cheat-safety guarantee.

`verify_profile(destination)` detects changed or newly added source files and
changed baseline/configuration/merged output. Missing files also prevent
verification. Runtime integration must call it immediately before launch and
refuse a stale profile. Hashes detect changes; they do not authenticate untrusted
mod authors or make native mods safe to execute.

Exports are bounded to 64 mods, 4096 input files, 512 MiB of total source files
and 64 MiB per PARAM archive. Symlinks, junctions, overlapping roots and
case-insensitive filename collisions are refused. No implicit output history or
cache is created. Existing output folders are never overwritten. The eventual
managed lifecycle must keep only its current/previous generated profile and must
not delete user-selected source folders.

## Remaining integration and acceptance

Before replacing the old Apply workflow:

1. Build, bundle and verify the pinned DSR runtime with its launcher corrections
   and all dependency notices. Use the shared first-run and Updates machinery;
   no separate helper hunt for the player, and no automatic runtime updates.
2. Wire the shared mod list, enable/disable, ordering, dependency/conflict display
   and launch action to the backend. Persist explicit choices. Do not create a
   plugin-specific replacement UI. Import/archive discovery remains to be added.
3. Migrate existing deployments through verified restoration of their preserved
   original. A hash-preserved original is not automatically a pristine baseline.
4. Add real-mod fixtures/evidence across independent and overlapping gameplay,
   model/texture and unsupported structural changes. Do not check proprietary
   archives or executables into the public repository.
5. Verify rendered interactions, first-run packaging, actual DSR file redirection,
   modded launch, normal vanilla launch, disabling/removal and recovery. Game
   testing must remain separate from synthetic tests and source inspection.

No issue closure or completed-loader claim is justified until those gates pass.
