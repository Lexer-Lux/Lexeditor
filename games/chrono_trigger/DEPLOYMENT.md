# Chrono Trigger Steam deployment

Lexeditor edits Chrono Trigger as archive-relative loose files (`Game/...`, `Localize/...`). CTExt can load those paths from `Chrono Trigger/mods/<mod-name>/` or from deterministic `.ctp` ZIP packages without rebuilding the installed `resources.bin`.

## Safety model

Lexeditor does **not** automatically install or replace CTExt runtime DLLs. An existing CTExt install must already contain:

- `ctext.dll`
- `sqlite3.dll`
- a readable `ctext.json`
- a documented `mods.enabled` boolean and `mods.load_order` string array

If that shape is not present, deployment fails closed.

The deployment manager:

1. audits the project against the current Steam archive and integrated cross-resource structures;
2. scans every scene header (not only the editor's 250-row page), de-duplicates referenced Atel scripts, validates world references, and rejects malformed structured overlays;
3. mirrors an external project to `mods/<project-folder-name>` or uses it in-place when the project is already under `mods/`;
4. refuses to overwrite a pre-existing mod folder unless it carries Lexeditor's own `.lexeditor-deployment.json` ownership manifest for the exact source project;
5. on redeploy, removes only files recorded in the previous Lexeditor manifest and leaves unrelated/manual files alone;
6. creates `ctext.json.lexeditor.bak` before the first Lexeditor load-order change;
7. enables CTExt mods and appends the project folder to `mods.load_order` without deleting/reordering existing entries;
8. supports explicit deactivation by removing only this project name from `mods.load_order` while leaving global `mods.enabled` alone;
9. supports undeploy for mirrored projects by validating ownership first, deactivating second, then removing only manifest-owned files;
10. never deletes a source project already located directly under `mods/<name>`; undeploy only deactivates it;
11. never modifies the installed `resources.bin`.

## Desktop path

The Chrono Trigger **Deployment** tab shows:

- CTExt runtime/config validity;
- selected project/deployed target;
- project audit errors, warnings and informational findings;
- whether deployment preflight is currently allowed;
- explicit Deploy & Activate.

Deployment is never a Save/Play/startup side effect. Deactivate/undeploy are currently exposed through the CLI while their desktop buttons remain a follow-up UI task.

## Command line

```text
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" status
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" audit
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" deploy
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" deactivate
python tools/chrono_trigger_ctext.py --game "D:\SteamLibrary\steamapps\common\Chrono Trigger" --project "C:\ChronoTriggerMod" undeploy
```

`deactivate` keeps deployed files and only removes the load-order entry. `undeploy` removes a mirrored copy only when its ownership manifest matches the selected source project.

## CTP export

`tools/chrono_trigger_project.py export-ctp` (and the desktop project workflow) creates a deterministic CTExt-compatible ZIP package with sorted archive-relative members and fixed timestamps. Lexeditor project/deployment metadata is excluded from the package.

## Audit severity

- `error`: deployment-blocking preflight problem, such as symlinked content, malformed scene/event/world structure, or unsafe project paths.
- `warning`: a proven reference is missing or a decoded field-event jump does not land on a command boundary.
- `info`: noteworthy but non-blocking state, including brand-new loose resources or scripts whose disassembly intentionally stops at an unknown/variable command.

Warnings do not automatically block deployment; errors do.
