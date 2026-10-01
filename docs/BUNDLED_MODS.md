# Bundled mods and linked tweaks

The shared mod library supports independently selected components of a parent
mod. A component's required tweaks and game payload are applied in one recoverable
transaction. These links are opt-in; Lexeditor does not invent links for existing
mods or execute scripts supplied by an imported package.

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
        "tweaks": ["combat.damage"]
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

## Trusted plugin registration

Register stable tweak IDs in `GamePlugin.bundled_tweaks`. Each value is a
`core.bundled_mods.BundledTweak(name, read, write)`. Both callbacks receive the
selected game root. `write` also receives the desired boolean. The plugin must
resolve its corresponding persistent configuration, use its existing tweak
implementation, and keep the original game behavior available when disabled.
Never choose a configuration file or executable callback from untrusted package
metadata. A read callback must not mutate anything.

Writes must be persistent, idempotent, and reversible through the same callback.
An exception can happen after a partial write; the shared transaction restores
the recorded prior values and prior deployment. It verifies each callback's
readback before accepting success. An ordinary tweak screen integrating a linked
tweak should call the shared host's `set_bundled_tweak` rather than writing its
setting independently. Direct external changes are detected in the library and
block host launch until the linked selection is applied again.

An adapter opts in with `supports_bundle_components = True` only when it consumes
the explicit component root list, retains stable folder IDs across reload, and
supports reapplying the previous selection after failure. The FF7R PAK adapter
uses this contract. Other adapters stay explicitly unsupported until integrated;
the shared bundle engine does not assume their project composers accept nested
roots. DS1 does not opt in and no DS1 loader is changed by this feature.

## Selection and recovery

The mod selector shows relationship help for bundle projects. Its Mod library
view lists component toggles and their assigned tweak names using shared
controls. Tweak-side toggles select or deselect all attached components. Apply
persists both sides together. A shared tweak remains enabled while any selected
component needs it; disabling it deselects all its dependents.

Selection is stored in `<library>/<game>/.bundles.json`. One bounded journal,
`.bundles-pending.json`, records the prior selection and tweak states before a
change. Normal failures restore both. If restoration fails or the process stops,
the journal remains and the library exposes Recover linked mods. New changes
and host launch are blocked until recovery succeeds. No unbounded backup history
or deployment copies are created by the shared bundle engine.

Checks: `tests/shared/test_bundled_mods.py` and
`tests/shared/verify_bundled_mods_ui.py`. Their packages and callbacks are
synthetic fixtures; they do not create a player mod or establish in-game
acceptance for a particular gameplay tweak.
