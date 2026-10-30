# Standalone mod folders

Players extract the loader package beside `DarkSoulsRemastered.exe`, then put
each prebuilt mod folder in that directory or its `mods` subfolder. Steam still
starts the game. The editor is optional, and no mod builder runs on the player's
machine.

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

Declarative layout and menu-command edits can start from another author's
structurally valid installed menu. Its exact bytes become the preserved
baseline, verified by the ownership journal; disabling these edits restores
that baseline. Missing anchors identify the affected mod before deployment.
Later edits to a file already managed by the loader are kept and reported,
never overwritten. An unowned backup that disagrees with the installed file
also needs reconciliation before either copy can be replaced.

This implements the current drop-in/install/adopt workflow. Older issue #954's
C-only port and rebasing full archive contributions over unrelated whole-file mods
are separate requirements; this implementation does not claim those completed.
