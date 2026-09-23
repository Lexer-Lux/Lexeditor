# RDR2 plugin

This directory contains the RDR2 plugin for Lexeditor. It owns the RDR2 page
composition, theme, local API, parsers, schemas, localization data, and visual
assets. The selected RDR2 project supplies the mod data that the plugin edits.

The plugin uses the shared WebView2 host and the shared components under
`C:\Lexeditor\ui`. Its dark gold-and-red interface preserves the former
standalone RDR2 editor layout.

The header `?` opens the RDR2 Data Map. The map reads the selected project's
`DATA_MAP.md` and shows Filename, What it controls, Notes, and Lexeditor edit
status. Integrated and partially integrated filenames open the applicable
editor page. The main navigation has no Data Map tab.

## Fonts

The RDR2 skin uses `Redemption` for display text and `RDRLino-Regular` for
ordinary interface text. The release does not bundle the font binaries.
Lexeditor downloads missing files from Rockstar's official media host when
RDR2 opens for the first time. The main-menu font button shows the installed
count and retries missing files. Downloads use pinned SHA-256 values and do not
need a Windows font installation. See `assets/fonts/README.md` for the fallback,
error-log, and redistribution boundaries.

## Start and check

From `C:\Lexeditor`:

```powershell
.\.venv\Scripts\python.exe app.py --game rdr2
.\.venv\Scripts\python.exe app.py --game rdr2 --check
.\.venv\Scripts\python.exe app.py --game rdr2 --smoke
```

The smoke check uses a temporary copy of `GameplayTweaks.ini`. It does not
change the live INI or the game directory.

## Paths

- `LEXEDITOR_RDR2_PROJECT` selects the RDR2 project. The default is
  `C:\RDR2Mod`.
- `LEXEDITOR_MOD_ROOT` selects the editable LML mod. The default is the
  project's `MyOverhaul` directory.
- `RDR2_GAME_ROOT` selects the game directory when a feature needs installed
  game data.
- `LEXEDITOR_RDR2_EXTRACT_ROOT` selects the prepared-data cache. The shared
  launcher sets it to `%LOCALAPPDATA%\Lexeditor\game-data\rdr2`.
- `LEXEDITOR_RDR2_PORT` selects a fixed loopback port. Lexeditor normally
  selects a free port for each session.

On first setup and each startup scan, Lexeditor validates `RDR2.exe` and the
`common_0.rpf`, `update_1.rpf`, `update_3.rpf`, and `update_4.rpf` sources. The
bundled read-only `RpfCli` prepares 28 required outputs for the active Items,
Effects, Loot, Challenges, Weapons, Crime, Bounty Hunters, Ped Perception,
Combat, and Ped Health pages. This includes the effective seven-layer weapon
definition stack and four weapon-component layers.

The version 5 manifest records dependencies for each output. Tool and snapshot
files use full SHA-256 hashes. Large installed archives use a bounded content
fingerprint in addition to size and modification time. A changed archive
rebuilds only the outputs that use that archive. Missing, invalid, or
unsupported data keeps RDR2 in Warning and names the failed file. The launcher
does not report Ready or allow the card to open until preparation succeeds.
Prepared data stays under Lexeditor's private cache. Missing or stale files are
replaced atomically. The source RPF files stay read-only.

The bundled RpfCli 1.2 can also extract named folders, follow nested RPF8
archives, and convert RBF resources to editable XML. Its commands are documented under
`tools/rpf-cli/README.md`.

## Item model previews

The Items eye control first checks the installed archive index. It stays
disabled when the model is not in an archive or format that the viewer supports.
This check does not extract the asset. Opening an enabled eye extracts only that
item and its referenced textures, then caches the converted preview under
`%LOCALAPPDATA%\Lexeditor\game-data\rdr2\model-previews`.

The resolver supports weapon YDR models and pickup YDR or YFT models. YFT
conversion reads the embedded drawable and texture dictionary. The renderer
supports `standard_weapon_2lyr`, `standard`, and `standard_dirt` materials. It
does not use substitute geometry or an item icon when a model cannot be decoded.

Weapon and catalog YMT resources can be binary `PSIN` after extraction. `PSIN`
is not RBF. For the supported game build, Lexeditor checks the extracted PSIN
hash and uses only its matching validated XML baseline. An unknown source hash
is rejected. Lexeditor never presents raw PSIN as editable XML.

Do not copy this implementation into an RDR2 project. Project verification and
asset tools must use this plugin directory as their editor source.
