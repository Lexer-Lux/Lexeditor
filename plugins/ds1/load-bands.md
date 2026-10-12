# Editable equipment-load bands

Dark Souls Remastered's Encumbrance editor exposes one to 32 load bands. Select
a mod project, open **Encumbrance > Bands**, and edit the selected band's name,
inclusive upper load percentage, movement profile and stamina recovery. Lower
limits follow the preceding band. The final band has no upper limit.

**Add band** splits the selected range. Both new ranges initially use the same
properties. Adjacent bands with the same movement profile share their movement
interpolation domain, so a split alone does not reset interpolation or recovery.

**Delete band** combines the range with an immediate neighbour. Both the
neighbour and the properties to keep must be selected explicitly. The preview
shows the resulting range, name, movement and recovery. The neighbour retains
its identity. The last remaining band cannot be deleted.

Special-light and forced-overburdened conditions are separate **Overrides**,
not additional numeric load bands. They have independent recovery settings.
Profiles use existing game behaviour, not new animations or invincibility
timings. **Misc.** contains the actual base regeneration before effect bonuses.

## Projects and library tweaks

New projects use vanilla native values: base recovery 45, ordinary thresholds
25%/50%/100%, and ordinary recovery percentages 100/100/80/70. Special-light
recovery is 100%. No balance preset is applied by opening or saving the editor.

Save writes the selected project. **Information > Apply** composes its saved
native rules with enabled library tweak mods, then installs the parameter
archive. Library **Tweaks** keeps master's schema-driven interface.
Rebuilding the tweaks on Save retains the last explicitly applied native project rules.
Resetting the project's native values to vanilla and applying removes that
contribution without disabling independent library tweaks.

**Restore original** restores the owned executable and parameter archive.
Saved projects and library switches are unchanged. Conflicting native edit
spans are refused before an installed file changes. PARAM archives remain
single-project replacements; this feature does not implement multi-mod PARAM
merging.

## Settings and earlier drafts

Current project settings use `.lexeditor-ds1-native-rules.json`, schema 1.
Band IDs are stable and never reused after deletion. Add/delete operations
carry a revision to reject stale structural edits. Read-only Vanilla cannot
write settings or change bands.

`legacy_stamina.py` reads the earlier `.lexeditor-ds1-stamina.json` schemas
without running a preset. Active native values migrate in memory; the old file,
including its inactive values, is retained. A changed save writes the new file.
The old draft's shield overlay is not applied: Effects remains the authored
source, with an explicit migration notice in the Apply confirmation.
Changing an authored effect never starts a hidden shield override.

An installed draft patch must first use **Restore original**, which verifies
its earlier backup and ownership. New Apply uses the shared native composer,
never the earlier standalone installer. Earlier backups are retained, not
silently overwritten or treated as unrelated shared-composer output.

## Native projection and ownership

Only the identified Remastered executable is supported. Its size is 50,286,344
bytes and SHA-256 is
`a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`.
No proprietary executable or archive is distributed.

`load_bands_patch.patch_spec(original, rules)` produces an original native
patch description. Vanilla values produce no changes; base-only edits need no
band code. Variable bands use one bounded 8 KiB island containing leaf
selectors, a maximum-32-row table and validated settings. The shared
`exe_patches.py` composer allocates it together with other mods and relocates
the classifier, recovery call and in-place table references.

The composer owns the combined PE layout. Original certificate bytes remain
preserved; executable modification does not retain a valid signature. Existing
nonleaf frames remain intact. The older section-extending projection in
`stamina_patch.py` is retained only for identifying/restoring draft output.

The shared executable loader records completed and pending hashes in a bounded
manifest. It preserves one shared original and rejects foreign post-images.
A failed parameter operation attempts rollback only of the exact expected
native image. The two installed files are separate atomic replacements, not
one filesystem transaction. Retry Apply or Restore after an interruption.

## Checks and limits

Tests cover split/merge semantics, one/32 bands, stable IDs, schema validation,
migration, current HTTP routes, read-only and cross-origin protection, shared
composition, library/project independence, conflict rejection, pending
ownership, rollback and exact restoration. Assembly tests independently check
the encoder and its relocations. Optional private-image tests execute native
selectors, interpolation and the recovery call site in isolated subprocesses.

The browser check covers actual shared controls, selected-row highlighting,
add/rename/delete previews, 1000x700 layout, save/reopen/discard, and Vanilla.
CI artifacts identify their exact source head and include rendered screenshots.

These tests are not retail-game acceptance. Windows game startup, complete
animation behaviour, every effect's activation/stacking, in-game restoration
and multiplayer safety still require separate offline testing.
