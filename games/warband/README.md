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
normal shell Save then runs the selected project's Module System build.

## WSE2 setup

Warband's native module system is the mod mechanism. WSE2 is an optional runtime
helper, not a multi-mod loader. Lexeditor bundles the pinned
`wse2-1.1.5.1-lex1.zip` package under `games/warband/runtime/`; first install
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
tools\Warband-checks.cmd --checks-only
```

The smoke/fixture checks use temporary data and do not establish actual
Warband/Steam/WSE2 gameplay acceptance.

Paths default to the Steam Warband install and `C:\Users\Lexer\Warbandmod`.
Override them with `LEXEDITOR_WARBAND_ROOT`, `LEXEDITOR_MOD_PROJECT`, and
`LEXEDITOR_OUT`. Never use an existing `C:\Lexeditor` tree as a disposable
candidate directory; extract a candidate to a separate folder.
