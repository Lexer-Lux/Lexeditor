# Warband plugin

Warband runs in the shared Lexeditor WebView2 host. The plugin owns Warband
format knowledge, project/build behavior and its parchment/burgundy theme; shared
navigation, Table + Detail controls, history, Credits, Updates and project
selection come from Lexeditor.

## Editing

The regular pages cover Items, Troop Trees, Troops, Misc. and Tweaks. **Misc.**
contains the Module System record families that have safe format-specific
coverage: skills, quests, strings, source info pages, music, sounds, meshes,
factions, post-processing, parties/templates, map icons' common fields,
scenes/props, mission templates, game menus, presentations, tableaux, skins and
particle systems.

The shell's Map button opens the Data Map. A Structured/Partial row links to its
real editor. A Source only row can still open the complete source file, but raw
source access is not counted as structured integration. Operation-heavy
scripts/triggers/dialogs and order-sensitive animation sequences remain
source-only.

Structured Module System saves patch only changed field spans, keep record IDs
fixed, reject stale source, create a backup and preserve unmodeled fields. The
structured path deliberately accepts literal top-level records only. Real Module
Systems that generate entries through helpers or wrappers remain visible but
source-only for those records rather than being rewritten speculatively. The
normal shell Save then runs the selected project's Module System build.

### Flat Module System imports

**Find a Mod** also accepts real flat Warband Module System source trees such as
Persistent World / Rome at War layouts, including a repository root whose one
child is named like `Module System`. Lexeditor never rearranges or writes that
chosen source. It creates a content-addressed managed copy under the user's
Lexeditor application-data folder, places the copied sources in `ModuleSystem/`,
and records source/fingerprint provenance in `.lexeditor-warband-import.json`.

Only the managed copy's literal `module_info.py export_dir` is redirected to
`../Module/`. The generated wrapper `build.bat` runs one pass of Python
commands extracted from upstream `build_module.bat`; pause/loop/display commands
are omitted and any unknown batch command rejects the import instead of being
executed. Re-selecting an unchanged source tree reuses the existing managed copy,
so Lexeditor edits are preserved rather than overwritten by a fresh import.

## Theme and installed assets

The parchment/burgundy chrome is original CSS inspired by Warband's visual
language; it does not embed game artwork. When an installed copy supplies
`Data/font_data.xml` and `Textures/font.dds`, Lexeditor reads those files
locally and derives an alpha-only font atlas into the user's private
`LOCALAPPDATA/Lexeditor/game-data/warband` cache. No TaleWorlds font texture,
font data, or other game asset is committed or redistributed, and the UI falls
back to system fonts when the installed atlas is unavailable.

The plugin does not bundle Warband sound effects. Game-derived audio should only
be added through a rights-safe source or the same local installed-asset model;
the current theme makes no claim of proprietary sound coverage.

## WSE2 setup

Warband's native module system is the mod mechanism. WSE2 is an optional runtime
helper, not a multi-mod loader. Lexeditor bundles the pinned
`wse2-1.1.5.1-lex1.zip` package under `plugins/warband/runtime/`; first install
and repair are offline and happen only after the user presses the shared
Install/Repair action.

The managed package intentionally excludes WSE2's self-updating launcher.
Lexeditor never invokes it and does not silently update WSE2. The Updates drawer
shows installed, pinned and latest-upstream versions separately. Installation
verifies the package and every written file, backs up replaced files, records a
pending transaction for crash recovery and rolls back a failed install. See
`runtime/README.md` and `manifest.json` for the exact package provenance.

## Running checks

From an isolated Lexeditor checkout:

```powershell
.\.venv\Scripts\python.exe app.py --game warband
.\.venv\Scripts\python.exe app.py --game warband --check
.\.venv\Scripts\python.exe app.py --game warband --smoke
.\.venv\Scripts\python.exe tools\check_plugin.py warband
```

The smoke/fixture checks use temporary data and do not establish actual
Warband/Steam/WSE2 gameplay acceptance.

Paths default to the Steam Warband install and `C:\Users\Lexer\Warbandmod`.
Override them with `LEXEDITOR_WARBAND_ROOT`, `LEXEDITOR_MOD_PROJECT`, and
`LEXEDITOR_OUT`. Never use an existing `C:\Lexeditor` tree as a disposable
candidate directory; extract a candidate to a separate folder.
