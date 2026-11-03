# Bundled mods

One library mod with several selectable components. A bundle's `mod.json`
declares its components; each component is a folder inside the bundle that
the game's loader deploys on its own. Which components deploy is ordinary
tweak settings: one on/off field per component, rendered by the shared
tweak-settings UI from the schema `core/bundled_mods.py` derives, stored in
the bundle's own `settings.json` next to the mod. There is no separate
dialog, no Apply step and no library-wide bundle state: ticking a component
saves it like any other setting through `save_mod_settings`, and the game's
loader reads the saved selection the next time it deploys. A tick deploys at
once while its bundle is on, like a switch; while the bundle is off the
saved tick waits for its switch.

A component's `tweaks` list is inert: it once named callbacks the game
registered in-process, which no game does. The format is still validated so
old bundles keep importing; nothing reads the names.

## Package format

Declare components in the parent's `mod.json`:

```json
{
  "name": "Example collection",
  "bundle": {
    "version": 1,
    "components": [
      {
        "id": "combat",
        "name": "Combat changes",
        "path": "components/combat",
        "tweaks": []
      }
    ]
  }
}
```

Each component folder is a complete payload accepted by the game's existing mod
adapter. The parent is a container, not another payload. Include any common
payload as an explicit component. Component paths cannot escape the parent,
overlap, or traverse links. Component folder names must be distinct among the
active mods because existing adapters use folder names as deployment IDs.
Imports retain the complete package; partial bundle imports are rejected.

## Selection and deployment

The Mods tab shows a bundle's components in its details SETTINGS section,
through the same shared settings surface as a tweak mod's settings. The host
expands each enabled bundle to its ticked components' folders before calling
the loader, so the loader keeps receiving plain mod folders. A component
starts off: enabling a bundle never deploys a part the reader did not tick.

An adapter opts in with `supports_bundle_components = True` only when it
consumes the explicit component root list and retains stable folder IDs
across reload. The FF7R PAK adapter uses this contract; a bundle on a loader
without component support is refused the same way its import is. DS1 does
not opt in and no DS1 loader is changed by this feature.

Checks: `tests/shared/test_bundled_mods.py` (schema, values, expansion and
the host save/deploy paths), `tests/shared/test_library_dissolve.py` (the
dialog and its backend are gone while drop import, upload and the library
location stay), and the Mods tab settings test in
`tests/shared/test_mods_tab.py`. Their packages are synthetic fixtures; they
do not create a player mod or establish in-game acceptance for a particular
gameplay tweak.
