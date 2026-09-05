# Lexeditor

Lexeditor is one desktop editor for Lexer's game mods. It uses one WebView2
window and one shared UI framework. Each game is a plugin.

## Shared framework

The [UI manual](docs/UI-MANUAL.md) defines the shared panel, Table, Detail,
reference, Thing Selector, and project concepts used by every plugin.

Both game plugins use the same code for:

- the desktop host and game switcher
- tabs, lists, sortable tables, pagination, and list-detail views
- one per-game Data Map opened by the header `?`
- scrolling, forms, dialogs, search, and common controls
- global Save, Undo, Redo, dirty state, and edit history
- plugin discovery, local-service startup, switching, and shutdown

Lexeditor calls a full-width record grid a **table view**. It calls a selectable
list on the left with the selected record's editor on the right a
**list-detail view**.

Game screens use a two-row shared header. Undo, Redo, the compact plugin
context, Save, plugin Settings, and Data Map help stay on the left of the top
row. Native window controls stay at the far right. The full-width tab row sits
below them and wraps whole one-line tabs instead of scrolling or hiding any
tab.

Each plugin defines its own pages, fields, actions, data adapters, and theme.
RDR2 keeps its dark gold-and-red layout. Warband uses its parchment and
burgundy layout. A shared component change applies to both games. A theme
change applies only to that game.

Game fonts style words only. Common icons and controls use a shared Windows
symbol font so a game's custom character mappings cannot replace arrows,
check marks, Save, Undo, Redo, help, or pagination symbols.

The main menu is neutral application UI. It uses charcoal and gray surfaces
with Windows system fonts and does not inherit any game theme. Green, yellow,
and red card trim shows installation status only.

Each card names its game once. It omits generic editor descriptions and keeps
only setup status, the selected path, its next action, and game-font status.

A plugin can also declare a Lexer-owned GitHub repository. If GitHub CLI is
installed and its active `github.com` account is an allowed owner, that card
shows a `GITHUB` button which opens the repository's Issues page. The host
checks the account again on click. Logged-out users, other accounts, and games
without a configured repository see no button. Lexeditor does not copy, log,
or store the GitHub token.

## Game setup

The main menu shows one state for each game:

- **Added** has green trim. Its saved directory and required data are ready.
- **Warning!** has yellow trim. A saved game moved, required files are missing,
  or data preparation failed.
- **Not added** has red trim. Lexeditor has no saved directory for the game.

Cards sort as Added, Warning, and Not added, then by game name. A card shows
when Lexeditor is scanning or preparing data. Lexeditor rescans every added
game when it starts. It checks known launcher records, Steam libraries, and
standard install paths on a background thread. It does not search a complete
drive recursively.

Click a warning or scanning game to see the problem and select the game folder.
A manual selection overrides any older automatic scan. Click a not-added game
to start its first setup scan. Lexeditor saves selected directories in
`%LOCALAPPDATA%\Lexeditor\game-installations.json`.

Each card has an `Aa X/Y` game-font status. Hover or focus it to see the full
status. A complete count is read-only. If a font is missing or a previous
download failed, click the control to retry; download progress stays visible
in the same tooltip.

RDR2 setup prepares the complete vanilla reference set used by its active
editor pages. It extracts XML and RBF data directly into Lexeditor's private
cache. For the PSIN catalog and weapon resources, it verifies the exact
installed source hash and converts the installed data with the bundled,
licensed reader. An unknown game build stays in Warning instead of receiving
guessed data.
It extracts missing or stale files from the required RPF archives into
`%LOCALAPPDATA%\Lexeditor\game-data\rdr2`. The game card stays busy and cannot
open until preparation succeeds. Source RPF files remain read-only.
The bundled extractor is an AGPL-3.0 separate process; its source, notice, and
license are under `tools\rpf-cli`. Version 1.3 can extract one named entry or a
named folder, follow nested RPF8 archives, and convert extracted RBF and PSIN
resources to editable XML without OpenIV.

Rockstar weapon and catalog YMT resources can use the binary `PSIN` format.
`PSIN` is not RBF. The bundled converter preserves unresolved schema members by
their exact hashes and resolves only licensed names plus the field contract
already used by the RDR2 plugin.

## Layout

    app.py             plugin discovery and command-line entry point
    desktop_host.py    the one WebView2 window and plugin lifecycle
    plugin_api.py      game-plugin contract
    service_session.py shared local-service lifecycle
    ui/                shared components, theme tokens, and game chooser
    games/rdr2/        RDR2 pages, theme, data service, parsers, and assets
    games/warband/     Warband pages, theme, data service, and parsers
    out/               generated reports and WebView2 profile data

The plugins own game-specific file formats. They do not create separate
desktop windows.

Paged views use one shared full-width footer bar. It stays fixed to the bottom
edge while its first, previous, direct-page, next, and last controls remain
centered.

## Install and start

Run this once to create the private Python environment and the Desktop and
Start Menu shortcuts:

    powershell -ExecutionPolicy Bypass -File install.ps1

Then start `Lexeditor.cmd`. You can also select a game directly:

    .\.venv\Scripts\python.exe app.py --game rdr2
    .\.venv\Scripts\python.exe app.py --game warband

Checks:

    .\.venv\Scripts\python.exe app.py --list
    .\.venv\Scripts\python.exe app.py --check
    .\.venv\Scripts\python.exe app.py --game rdr2 --smoke
    .\.venv\Scripts\python.exe app.py --game warband --smoke
    .\.venv\Scripts\python.exe app.py --smoke-host

The service smoke checks edit temporary settings files. The host smoke check
opens a hidden WebView2 window, switches from RDR2 to Warband in that same
window, and confirms that the old service stops. It also confirms that
Maximize uses the Windows work area, that Restore recovers the prior window
rectangle, and that the running window has the Lexeditor taskbar identity and
native icons.

## RDR2 plugin

The RDR2 plugin preserves the former standalone editor interface while it uses
the shared shell and components. Its visible navigation supplies 11
game-specific pages for AI, challenges, crime, crafting, effects, items, loot,
mobs, shops, settings, and weapons. The header `?` opens the RDR2 Data Map;
there is no Data Map tab.

The project defaults to `C:\RDR2Mod`. Set `LEXEDITOR_RDR2_PROJECT` to select a
different project. Set `LEXEDITOR_MOD_ROOT` to select a different editable LML
mod directory. The shared launcher sets `RDR2_GAME_ROOT` to the selected game
directory and `LEXEDITOR_RDR2_EXTRACT_ROOT` to its private prepared-data cache.

Catalog items show an eye control only when their model exists in an archive
that the viewer supports. It opens a rotatable and zoomable view of geometry
extracted from the installed game on demand. The
header Settings gear sets the preview-cache limit and clears generated preview
data. The cache is under
`%LOCALAPPDATA%\Lexeditor\game-data\rdr2\model-previews`; Lexeditor does not
pre-extract the game's model library. The resolver supports textured weapon and
pickup YDR models, plus pickup YFT models with embedded drawables. It translates
the `standard_weapon_2lyr`, `standard`, and `standard_dirt` material families
and has no per-item preview table. Unsupported archive locations, formats, and
shader families keep the eye disabled.

## Warband plugin

The Warband plugin uses the same framework with its own theme and page layout.
It supplies item, manual, troop-tree, troop, tweak, settings, and build pages.
The header `?` opens the Warband Data Map; there is no Data tab. Its previous
Tkinter window is retired.

Each Data Map has four columns: Filename, What it controls, Notes, and Status.
Status means whether that file can be edited in the selected game's
Lexeditor. A check means integrated, an X means not integrated, and the split
check/X mark means partial support. Editable filenames open their editor.

Warband paths default to the Steam install and
`C:\Users\Lexer\Warbandmod`. You can override them with
`LEXEDITOR_WARBAND_ROOT`, `LEXEDITOR_MOD_PROJECT`, and `LEXEDITOR_OUT`.

The Warband Module System still requires Python 2.7. Lexeditor itself uses its
private Python 3 environment.

## Safety

- Services listen only on loopback and stop when the host closes or switches.
- The main menu and game screens use one shared frameless-window implementation.
  A normal launch opens restored with Minimize, Maximize or Restore, Close,
  title-area movement, and eight edge or corner resize handles. Maximize fills
  the usable monitor area and leaves the Windows taskbar visible.
- The host sets the Lexeditor AppUserModelID and native icon before the window
  appears. Installed shortcuts run the private `pythonw.exe` directly, without
  a console window.
- A failed game start leaves the current game service running.
- Switching games asks before it discards unsaved changes.
- Settings and editable source files get `.lexeditor.bak` backups.
- Python source saves use Python 2 syntax validation when Python 2.7 is present.
