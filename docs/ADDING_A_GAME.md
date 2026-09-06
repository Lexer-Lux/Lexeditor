# Add a game to Lexeditor

A game plugin owns game detection, data parsing and safe project output. The shared
shell owns navigation, windows, settings, history and common controls. Start with
`games/blank` for UI examples; use `games/ff7` or `games/ff9` for an editable project.

## 1. Register the plugin

Create `games/<game>/__init__.py` and `plugin.py`. Export one `GamePlugin` named
`PLUGIN` from `plugin_api.py`. The application discovers these files automatically.
Give it a unique letters/numbers/hyphens ID, name, subtitle, description, accent,
`check`, `launch` and a `session_factory`. Use repository-relative absolute paths
for packaged resources; use a per-user directory for writable files. `check()`
returns readable problems without modifying the installation.

```python
from pathlib import Path
from plugin_api import GamePlugin
from service_session import LocalPluginSession

ROOT = Path(__file__).resolve().parents[2]
def check():
    return []  # Replace with actual checks; do not invent readiness.

def session(extra_env=None):
    return LocalPluginSession(module="games.example.server", plugin_id="example",
                              app_root=ROOT, check=check, extra_env=extra_env)

def launch():
    from desktop_host import run_host
    return run_host({"example": PLUGIN}, "example")

PLUGIN = GamePlugin(plugin_id="example", name="Example", subtitle="Example game",
                    description="Edits the supported Example records.", accent="#557788",
                    check=check, launch=launch, session_factory=session)
```

Register the server module in `runtime_bootstrap.SERVICE_MODULES` as well: frozen
applications allow only explicitly bundled child services. Add attribution and
local notices under your plugin ID in `ui/credits-sources.json`. Run
`python tools/generate_credits.py` to rebuild the offline bundle;
`python tools/generate_credits.py --check` checks it without modifying files.
The credits validator rejects missing plugin entries. Do not package game assets or unlicensed helpers.

## 2. Describe the installation and editable project

Use `GameInstallSpec` for the game-root environment variable, Steam application
ID, recognized directory names and required relative paths. Add a preparation
callback only for supported extraction. Never report a path as usable merely
because a folder exists. A helper integration supplies `helper_name`, separate
`helper_status`, explicit `helper_install` and read-only `helper_upstream` callbacks.
Keep the pinned, installed and newest upstream versions distinct.

Use `ModProjectSpec` for the separate mod-root environment variable, validation
paths, template and optional initializer. Parsing reads the installation; saving
writes a project overlay. Validate bounds, enums and source hashes, preserve
unknown fields, and test round-trip writes. Do not overwrite the installed archive
as an editor save. Blank intentionally has no disk-backed mod project.

## 3. Serve the editor

The child service listens on **127.0.0.1** at `LEXEDITOR_PORT`. Serve `/api/plugin`
with at least `pluginId`, `hosted: true` and accurate capabilities; the session
supervisor rejects a different identity. Serve the editor at `/` and shared assets
under `/shared/`, with resolved-path containment checks. Never expose arbitrary
filesystem paths through an HTTP route. Stop the service when its host exits.

Load `/shared/framework.css` and `/shared/framework.js`, then call
`LexeditorUI.mountShell` with the plugin descriptor, tabs, navigation, dirty count,
undo/redo history and save/discard callbacks. Provide `info`/`infoActive` callbacks
for the shared Credits section. Use `detailField`, `columnList`, `pagedListDetail`
and `pager`; do not recreate them separately in each plugin. Booleans use
checkboxes, enums use selects, and numbers use real bounds and units.

Every game needs a **Data Map**. Distinguish fully editable, partially editable and
unsupported data, with the actual editor action or remaining limitation. A raw
file viewer or export tool is not a structured editor. Keep record identity in the
master list and editable fields in the detail pane. Use concise help that describes
the actual effect, unit, special values and restart requirement.

## 4. Verify before shipping

Run `python app.py --list` and `python app.py --game <id> --check`. Supply a safe
`smoke()` callback before using `--smoke`; use generated fixtures, not destructive
operations on a real save. Add malformed-input, bounds, round-trip, project-isolation
and service-shutdown tests. Check resizing, keyboard navigation, sorted selection,
empty lists and unsaved-change guards in a browser and the native host.

Add the plugin to frozen-app tests and verify its server module starts from the
packaged executable. A passing parser test is not visual or in-game acceptance.
Preserve the original issue request and record implementation evidence in its
existing worklog. Keep the human-facing issue short, with a usable acceptance
checklist only when its test candidate is actually available. Follow `AGENTS.md`;
the separate codex/worklog consolidation task is not part of adding a plugin.
