# Editable equipment-load bands

This extends the earlier fixed-class Encumbrance editor in PR #906, related to #758. Effects and Misc. remain available.

## Editing

Enable **Encumbrance rules** in **Tweaks**, then open **Encumbrance > Load bands**. Each band has a name, an inclusive upper load percentage, an existing movement profile, and an independent stamina-recovery percentage. The final band has no upper limit. Between 1 and 32 bands are supported.

**Add band** splits the selected range at the chosen percentage. Both resulting bands initially have the same properties. Adjacent bands with the same movement profile share their interpolation domain, so splitting alone does not reset movement interpolation or change recovery.

**Delete band** merges the selected range into an immediately adjacent band. The user must choose the neighbour and whose properties survive. The neighbour keeps its identity. The preview shows the combined range and surviving properties before confirmation. The last remaining band cannot be deleted.

Special-light and forced-overburdened conditions are effect-driven overrides, not ordinary equipment-load ranges. They have separate recovery settings under **Overrides**. Existing movement profiles are reused; this does not create new animations or editable invincibility frames.

Save changes the isolated project. Apply deploys the saved rules with the game closed. Disabling the tweak retains authored bands in the project and restores native defaults on Apply.

## Persistence and protection

Schema 1 settings migrate in memory without changing their thresholds or recovery values. They are written as schema 2 on a later changed save. Band identities are stable, newly created identities are not reused after deletion, and structural requests carry a revision so stale split/merge requests are refused. Read-only Vanilla remains protected.

## Native implementation

Unlike the original fixed-class implementation, variable bands extend the last executable section by a bounded 8 KiB. This holds two original leaf routines, a maximum-32-row table and validated settings. The certificate overlay is preserved and moved, with its file pointer updated. Modification invalidates the executable signature; no bypass is supplied.

The original build fingerprint, verified backup, owned-image reproduction, guarded Apply, and restoration remain mandatory. Fixed-class installed projections remain readable. Default rules use the existing no-op path. Only the identified Dark Souls Remastered executable is supported.

## Verification status

The continuation's `test_ds1_load_bands.py` passed 53 tests on Linux x86-64 with GCC and the private identified executable. This covers validation, split/merge preservation, migration values, independent recovery, bounded tables, compiled classifier/recovery selectors, original-versus-patched classifier comparisons, certificate preservation and unchanged bytes outside declared spans. No proprietary image is committed.

The integration fixture, native-rule integration tests and rendered browser check have been updated for variable bands. Their current-head full CI and rendered acceptance still require verification. Earlier browser/native test totals are historical, not substituted for this head. Windows game startup, real gameplay, animation behavior and offline restoration remain unverified. Native function execution does not establish retail-game acceptance or multiplayer safety.

## Shared-composer export

`load_bands_patch.patch_spec(original, rules)` now exports a versioned patch
description for the native composer from master, rather than another complete
executable. It returns no edits for vanilla rules and only a baseline edit when
the load rules are unchanged. The expected hook bytes come from the caller's
fingerprinted original; no proprietary original bytes are embedded in source.

The code and table form one movable island. The composer relocates the
classifier branch, the recovery call and the three in-place table references
after allocating every enabled patch. The existing nonleaf frames and their
unwind records do not move. It retains the original certificate bytes and owns
the single combined PE layout. As with any executable modification, this does
not retain a valid signature or establish online safety.

Description version 2 adds bounded hook displacements targeting an island in
the same description. Version 1 remains readable. Version 2 is deliberately
rejected by an old composer, rather than silently ignoring its relocations.
Overlapping displacements, out-of-island targets, duplicate owner/island
identities and conflicting original edit spans are rejected.

Synthetic tests exercise placement after zero-, 16- and 4096-byte independent
islands, no-op/base-only export, conflict and malformed-input rejection.
An independent assembler check matches the displacement offsets to the
assembly relocation records. The optional private-image child-process check
executes the composed classifier, recovery selector, full recovery call site
and interpolation body across eight configurations, including one and 32
bands, split ranges and special/forced conditions.

This is an export/integration step, not a completed deployment migration.
`StaminaRebalance.apply` still uses the legacy ownership path. Before merging,
reconcile it with master's library-mod Tweaks UI, shared native installation,
and migration of existing verified originals without losing user settings.
The legacy installer must not be called on a shared-composer image. No
installed-game startup, animation, or multiplayer acceptance is claimed.
