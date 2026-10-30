# Standalone mod folders

Players extract the loader package beside `DarkSoulsRemastered.exe`, then put
each prebuilt mod folder in that directory or its `mods` subfolder. Steam still
starts the game. The editor is optional, and no mod builder runs on the player's
machine.

The online and debug loaders apply the shared patch only after preparation
succeeds for this launch. A failed or unavailable helper leaves old shared
patches inactive while independent native-only folder modules can still load.
The basic proxy has no pre-entry preparation callback and loads native-only
folder modules without using a previous shared patch.

Native installation compares bounded snapshots before writing. A caught write
failure restores the exact previous DLL, patch, record and configuration. A
later deployment failure uses the same receipt, preserving metadata extensions
and legacy project selections. Restore retains rollback across data, menus and
loader removal. Unexpected external changes are preserved and reported.
An abrupt process exit leaves each individual file atomic. The last committed
record retains its legacy project selection, startup regenerates shared support
and data, and a later Apply repairs an interrupted loader/record pair.

If another mod already installed `dinput8.dll`, rename that other loader to
`dinput8.chain.dll` before extracting this package. The loader loads that DLL
before game entry and forwards its input calls, or uses system input when the
proxy has no input export. An unreadable, damaged or oversized chain is logged
and left on disk; system input remains available. Never overwrite an existing
chain, and do not rename Lexeditor's own loader into that slot.

The loader also reads the existing shared library, normally
`Documents/Mods/ds1`. Lexeditor writes its chosen location to
`lexeditor-ds1.ini`; it does not create a second managed library. On startup the
editor offers to move recognized standalone packages into that library. A move
is explicit, checks duplicate identities, verifies cross-volume copies, and
preserves the package's enabled state. Loose files cannot be reliably attributed
to one mod and are not offered for a move.

## Author builds

The editor watches mod files without restarting. A changed build input updates
rebuild status; changed records, maps, animation data or settings refresh a clean
project after the current control loses focus. Unsaved edits defer replacement.
All replacement data validates before the session swaps stores; damaged files
leave its current data intact. Notifications identify affected paths, so a
builder edit does not hash unrelated archives, and unchanged decoded animation
and map documents are retained.

Save/build the mod in Lexeditor, select it in Mods, then use **Export for
players** in its detail header. The ZIP contains the common loader and its
private runtime, plus `mods/<id>/` with that mod's prebuilt contributions.
Extract the ZIP into the game directory. Other required mods remain declared
in `mod.json`; install their releases too. Export does not enable or deploy
anything. Changed source/settings or missing built data must be rebuilt first.

The command-line tool exports only the mod folder, for authors distributing
the common loader separately:

    python tools/export_ds1_mod.py MOD_FOLDER --game GAME_FOLDER --output RELEASE.zip

The export contains `mod.json`, a prebuilt `runtime.lxd`, and the data
contributions the mod actually uses. Settings are baked into the exported
payload. Tests, research notes, builder source, bytecode caches and local build
journals stay out. Dependencies from metadata and the settings schema remain
declared in the exported metadata.

Native properties edited in the editor travel as generated
`native-support/native-rules.json`, alongside their saved values. The shared
runtime links those prepared patch bytes beside the mod's `runtime.lxd`; it
does not run the author's builder. Importing a release retains its editable
property values. Export regenerates this contribution from the saved values
and preserves existing prebuilt machine code and relocations. A missing or
stale property contribution disables its owning mod before data is deployed.
Library switches control these properties too; an old global project recipe
for the same library folder is retired so an unchecked mod cannot stay active.

Parameter and item/menu text contributions use `records.lxd`: only changed
rows and text entries, with their old values as anchors. They preserve other
installed fields and records instead of treating a complete archive as this
mod's intent. A mismatching field or missing record identifies that mod and
prevents its partial deployment. Imported releases use those same records in
the editor, including added/edited markers; saving keeps the portable format.
Map releases use the map adapter's editable field spans and baseline anchors.
Independent placement, region and event fields preserve unrelated installed
edits. Structural changes retain an exact whole-map anchor and refuse a
different installed baseline. Imported maps remain editable and save into the
same portable record file as item changes.
Event archives also carry only changed EMEVD event records. Their unchanged
string/link pools are anchored, independent constructor additions use the
existing event merger, and foreign records and appended pools are preserved.
Changes requiring relocation of opaque string arguments are refused at export.
Loose ESDs and talk/menu script binders carry changed states, commands,
conditions and member records. They use the existing structural ESD merger;
unrelated installed states, members and file metadata survive. Missing anchors,
conflicting changes or dangling final transitions refuse that mod before writes.
These changes also appear in the shared Records view.

Large record files use a bounded compressed envelope (64 MiB stored, 256 MiB
decoded); older JSON record files remain readable. This is versioned data and
cannot execute a builder.

Prepare the common loader package separately:

    python tools/package_ds1_loader.py --plan
    python tools/package_ds1_loader.py --output NEW_FOLDER

This copies the already-built online DLL, a private CPython runtime and the
shared data-composition engine. The package needs no installed Python, compiler,
pip, or Lexeditor UI. `Loader-credits.txt` and `Python-LICENSE.txt` carry the
licenses; the source of the composition engine travels with the private runtime.
The DLL's corresponding source and upstream licenses remain in this repository.

## Runtime

`runtime.lxd` wraps the existing `LXD1PAT` stream with link fixups, state claims
and a CRC. Mod code is already compiled. The loader assigns movable code separate
addresses and adjusts game-relative calls, hooks and unwind tables together.
Fixed code retains its declared address. Identity, format, size, original hook
bytes and conflicting claims are checked before that module's hooks change.
Malformed, disabled, missing-dependency and conflicting modules are skipped with
named log messages; unrelated modules continue. Code is changed in memory only.

The editor never writes, renames or deletes the game executable, including
legacy recovery. Steam verification handles a modified executable. Old native
backups and journals remain untouched and cannot block an already-verified
image. Restore removes owned loader files and restores managed data even when
the executable was changed. Asset mods cannot supply executable replacements;
the failing mod is isolated before deployment. Asset enumeration and input
reads are bounded, and private backup/bytecode artifacts are excluded.

The online/debug loader's pre-entry callback runs the private data merger before
the game opens its data. It uses the same `mod_loader`, menu and deployment code
as Lexeditor, rather than maintaining a second composer. Prebuilt parameter,
text, map, character, event and menu contributions combine through those
adapters. The merger never imports a mod's builder. Corrupt composition reports
are disposable; unchanged inputs reuse installed results. Identified failures
disable that mod and missing dependents instead of preventing unrelated mods
from loading. The basic proxy package supports native-only mods; standalone
distribution uses the online package and its existing save/reporting protection.

Runtime logs and composition reports are bounded. `lexeditor-ds1-load.json`
records data preparation and disabled mods; `lexeditor-ds1-patch.log` records
native loading. Data-dependent native modules do not load if preparation fails.

Editor and standalone composition share the bounded archive cache. A cache
hit skips portable-record materialization and archive rebuilding. Disk holds
at most 512 outputs and 512 MiB of payload; the memory cache stays at 128 MiB.
Corrupt, oversized or incompatible disposable databases are recreated. A busy
database is left alone, and cache failures fall back to normal composition.
Source identity is independent of where the same engine is installed.

Declarative layout and menu-command edits can start from another author's
structurally valid installed menu. Its exact bytes become the preserved
baseline, verified by the ownership journal; disabling these edits restores
that baseline. Missing anchors identify the affected mod before deployment.
Raw/portable menu archives and declarative edits compose over that same
baseline before a single menu writer deploys them. The generic data writer
cannot overwrite or restore those destinations. Legacy data ownership records
transfer to the menu journal after both original and installed hashes verify;
the transfer never changes game bytes. Restoring also handles these old records
when no native runtime was installed.
Later edits to a file already managed by the loader are kept and reported,
never overwritten. An unowned backup that disagrees with the installed file
also needs reconciliation before either copy can be replaced.

This implements the current drop-in/install/adopt workflow. Older issue #954's
C-only port and rebasing the remaining map/character archive contributions over unrelated whole-file mods
are separate requirements; this implementation does not claim those completed.
