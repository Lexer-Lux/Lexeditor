# Chrono Trigger Steam deployment

Lexeditor edits Chrono Trigger as archive-relative loose files (`Game/...`, `Localize/...`). CTExt can load those paths from `Chrono Trigger/mods/<mod-name>/` without rebuilding the installed `resources.bin`.

## Current safety model

Lexeditor does **not** automatically install or replace CTExt runtime DLLs. An existing CTExt install must already contain:

- `ctext.dll`
- `sqlite3.dll`
- a readable `ctext.json`
- `ctext.json` must contain the documented `mods.enabled` boolean and `mods.load_order` string array

If that shape is not present, deployment fails closed.

The deployment manager:

1. audits the project against the current Steam archive and integrated cross-resource references;
2. mirrors an external project to `mods/<project-folder-name>` or uses it in-place when the project is already under `mods/`;
3. refuses to overwrite a pre-existing mod folder unless it carries Lexeditor's own `.lexeditor-deployment.json` ownership manifest for the exact source project;
4. on redeploy, removes only files recorded in the previous Lexeditor manifest and leaves unrelated/manual files alone;
5. creates `ctext.json.lexeditor.bak` before the first Lexeditor load-order change;
6. enables CTExt mods and appends the project folder to `mods.load_order` without deleting/reordering existing entries;
7. never modifies the installed `resources.bin`.

## Command-line path

Until the same controls are exposed in the desktop Deployment screen, the first-party CLI provides status, audit, and explicit deployment:

```text
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" status
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" audit
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" deploy
```

`deploy` is explicit and one-shot. It is not run automatically by Save, Play, plugin startup, or project selection.

## Audit severity

- `error`: deployment-preflight problem that should block deployment (for example symlinked project content or a structured parser failure).
- `warning`: a proven reference points at a missing Steam/overlay resource (for example a scene's Atel script ID or a world's EventTable/script ID).
- `info`: valid but noteworthy state, including a brand-new loose resource or a world script whose disassembly stops at an unknown PC/DS opcode.

Warnings do not automatically block deployment; errors do.
