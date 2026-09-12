# Stardew Valley codex

Canonical research for the Lexeditor Stardew Valley plugin.

## Initial support target

- **Edition/build:** Stardew Valley PC, current stable **1.6.15**. Initial installation acceptance is Windows/Steam; other PC storefronts/platforms stay unsupported until their install/runtime paths are verified.
- **Loader/deployment:** target **SMAPI + Content Patcher** instead of replacing installed `.xnb` files. A Lexeditor project should be a normal Content Patcher content pack which can be copied into `<Stardew Valley>/Mods/`.
- **First vertical slice:** structured editing of the `Data/Objects` asset, serialized as Content Patcher `EditData` changes. The base game remains read-only.
- **Later surface:** other strongly typed 1.6 data assets (crops, big craftables, machines, weapons, shops, etc.), images, maps, dialogue/events, and richer Content Patcher conditions.

## Settled architecture

Stardew Valley stores game assets under `Content/` as XNB content. Direct XNB replacement is obsolete for this plugin: the Stardew modding documentation recommends Content Patcher or SMAPI's content API so the installed game files are not replaced.

Content Patcher is a SMAPI mod which applies content packs from the game's `Mods` directory. It supports data, images, maps, and dialogue. For structured data it exposes the `EditData` action, including field-level edits which allow multiple mods to change different fields of the same record without whole-file replacement.

Stardew Valley 1.6 moved many formerly slash-delimited data tables to strongly typed models and added/expanded assets such as `Data/Objects`, `Data/BigCraftables`, `Data/Machines`, `Data/Fences`, and `Data/FloorsAndPaths`. This makes those assets the preferred Lexeditor coverage surface.

`Data/Objects` is a string-keyed model lookup. Useful schema facts for the first editor include:

- `Name`, `DisplayName`, `Description`, and `Type` are textual/model fields.
- `Category` is a numeric item-category ID.
- `Price` is the player's base sell price and defaults to 0.
- `Edibility` defaults to -300; values at or below the documented inedible sentinel must be represented deliberately, not guessed.
- `IsDrink` is boolean.
- `Texture` and `SpriteIndex` identify the item's sprite source.
- `ContextTags` is a list and should eventually get list/semantic editing rather than a free-text blob.

Content Patcher's documented `EditData` shape uses a `content.json` root with a `Format` version and `Changes` array. An object field edit targets `Data/Objects` and places per-record field edits under `Fields`; this is preferable to replacing a whole record when only a few fields changed.

## Sources and licensing

These sources materially inform the plugin and must stay represented in Lexeditor Credits:

- Stardew Valley Wiki modding documentation — Content Patcher, XNB editing, Stardew Valley 1.6 migration, object/item data schemas. Documentation/reference only: <https://stardewvalleywiki.com/Modding:Content_Patcher>
- Pathoschild / Content Patcher — canonical content-pack and `EditData` behavior. Source repository is MIT licensed: <https://github.com/Pathoschild/StardewMods>
- Pathoschild / SMAPI — established Stardew Valley mod loader/runtime. Source repository is LGPL-3.0 licensed: <https://github.com/Pathoschild/SMAPI>

No SMAPI or Content Patcher source code is copied into Lexeditor by this initial implementation; they are external runtime/reference projects.

## Open work

- Verify exact Windows 1.6.15 installation signatures and SMAPI/Content Patcher installed-layout signatures against a real installation.
- Decide whether Lexeditor should invoke an existing XNB extraction tool, SMAPI itself, or a small helper to obtain base `Data/Objects` values for the read side of the vertical slice.
- Build the Data Map before broadening editors.
- Prove create/open/save/reopen/deploy/load for one `Data/Objects` field edit, with the installed game remaining byte-identical.
