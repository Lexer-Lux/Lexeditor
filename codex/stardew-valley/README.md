# Stardew Valley codex

Canonical research for the Lexeditor Stardew Valley plugin.

## Initial support target

- **Edition/build:** Stardew Valley PC, current stable **1.6.15**. Initial installation acceptance is Windows/Steam; other PC storefronts/platforms stay unsupported until their install/runtime paths are verified.
- **Loader/deployment:** target **SMAPI + Content Patcher** instead of replacing installed `.xnb` files. A Lexeditor project is a normal Content Patcher content pack copied into `<Stardew Valley>/Mods/` by the managed deployment path.
- **First vertical slice:** structured editing of the `Data/Objects` asset, serialized as Content Patcher `EditData` changes. The base game remains read-only.
- **Vanilla read source:** when present, Lexeditor reads `Content (unpacked)/Data/Objects.json` produced by StardewXnbHack. The JSON export and source XNB are never modified by the editor.
- **Later surface:** other strongly typed 1.6 data assets (crops, big craftables, machines, weapons, shops, etc.), images, maps, dialogue/events, and richer Content Patcher conditions.

## Settled architecture

Stardew Valley stores game assets under `Content/` as XNB content. Direct XNB replacement is obsolete for this plugin: the Stardew modding documentation recommends Content Patcher or SMAPI's content API so the installed game files are not replaced.

Content Patcher is a SMAPI mod which applies content packs from the game's `Mods` directory. It supports data, images, maps, and dialogue. For structured data it exposes the `EditData` action, including field-level edits which allow multiple mods to change different fields of the same record without whole-file replacement. Current Content Patcher author documentation uses content format **2.9.0**.

Stardew Valley 1.6 moved many formerly slash-delimited data tables to strongly typed models and added/expanded assets such as `Data/Objects`, `Data/BigCraftables`, `Data/Machines`, `Data/Fences`, and `Data/FloorsAndPaths`. This makes those assets the preferred Lexeditor coverage surface.

StardewXnbHack is the canonical first read-side bridge because the Stardew modding documentation recommends it over xnbcli for typed game-data models. It loads assets through Stardew Valley's own content runtime and writes data assets as JSON. Its normal export root is `Content (unpacked)`.

**Source-generation decision:** Lexeditor will not invoke StardewXnbHack automatically in this first slice. The helper's documented operation unpacks the full `Content` tree; it doesn't expose a documented single-asset `Data/Objects` command. Silently triggering a full unpack merely to populate one editor would be disproportionate and would create a large derived-data tree inside the installation. Lexeditor therefore consumes an existing export, reports clearly when it is absent, and keeps the source-generation step explicit until a genuinely narrow supported path exists.

`Data/Objects` is a string-keyed model lookup. Useful schema facts for the first editor include:

- `Name`, `DisplayName`, `Description`, and `Type` are textual/model fields.
- `Category` is a numeric item-category ID.
- `Price` is the player's base sell price and defaults to 0.
- `Edibility` defaults to -300; values at or below the documented inedible sentinel must be represented deliberately, not guessed.
- `IsDrink` is boolean and defaults to false.
- `Texture` and `SpriteIndex` identify the item's sprite source.
- `ContextTags` is a list and should eventually get list/semantic editing rather than a free-text blob.

Content Patcher's documented `EditData` shape uses a `content.json` root with a `Format` version and `Changes` array. An object field edit targets `Data/Objects` and places per-record field edits under `Fields`; this is preferable to replacing a whole record when only a few fields changed. The first editor therefore keeps vanilla values separate from project overrides and only serializes fields whose **Override** control is enabled.

## Installed acceptance contract

The editor has an explicit real-install acceptance flow instead of treating synthetic smoke tests as installation proof:

1. Save at least one supported `Data/Objects` field override and deploy the current project through Lexeditor.
2. **Begin Acceptance** verifies the deployed `manifest.json` and `content.json` match the current project, snapshots those project files, snapshots `Content/Data/Objects.xnb` by SHA-256, snapshots the current `SMAPI-latest.txt`, and snapshots any pre-existing Content Patcher `Data/Objects` export.
3. Launch Stardew Valley through SMAPI and reach the title screen so SMAPI discovers the content pack.
4. In the SMAPI console run `patch export "Data/Objects"`. Content Patcher documents this command as exporting the asset with all mod changes applied; for `Data/Objects` it writes JSON under the game's `patch export` folder.
5. **Verify New SMAPI Run** requires a genuinely new log, parses SMAPI's own runtime signature, requires Stardew **1.6.15** on Windows, verifies Content Patcher was loaded, verifies this project appears in SMAPI's `Loaded ... content packs` section as `for Content Patcher`, rejects project-specific load errors, checks SMAPI against Content Patcher's manifest-declared minimum API version when available, requires a fresh post-baseline `Data/Objects` export, compares every supported project override with the corresponding value in that exported post-patch asset, and confirms `Objects.xnb` is still byte-identical to the baseline.

This distinction matters: a content pack appearing in SMAPI's load list proves discovery, while Content Patcher's exported post-mod asset proves the actual `EditData` result. The harness records that evidence; it does not manufacture acceptance. The PR stays draft until this flow passes against a real Windows/Steam installation.

## Sources and licensing

These sources materially inform the plugin and must stay represented in Lexeditor Credits:

- Stardew Valley Wiki modding documentation — Content Patcher, XNB editing, Stardew Valley 1.6 migration, object/item data schemas. Documentation/reference only: <https://stardewvalleywiki.com/Modding:Content_Patcher>
- Pathoschild / Content Patcher — canonical content-pack and `EditData` behavior, plus the `patch export` post-mod asset diagnostic used by installed acceptance. Source repository is MIT licensed: <https://github.com/Pathoschild/StardewMods>
- Pathoschild / SMAPI — established Stardew Valley mod loader/runtime, including the canonical runtime and loaded-content-pack log formats consumed by the acceptance harness. Source repository is LGPL-3.0 licensed: <https://github.com/Pathoschild/SMAPI>
- Pathoschild / StardewXnbHack — canonical typed-asset unpacking behavior and `Content (unpacked)` layout. Source repository is MIT licensed: <https://github.com/Pathoschild/StardewXnbHack>

No SMAPI, Content Patcher, or StardewXnbHack source code is copied into Lexeditor by this implementation; they are external runtime/reference projects.

## Open work

- Run the installed acceptance flow against a real Windows/Steam Stardew Valley 1.6.15 installation with current SMAPI + Content Patcher, including a fresh `patch export "Data/Objects"` that proves a representative Lexeditor field edit is present in the post-patch asset.
- Broaden `Data/Objects` semantic fields only after the current vanilla-read/project-write/deploy/load/export path is accepted against a real installation.
- Expand Data Map coverage to the next typed assets after the Objects vertical slice is proven in-game.
