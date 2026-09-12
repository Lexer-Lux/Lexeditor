# Project Zomboid

Settled Project Zomboid knowledge used by the Lexeditor plugin. Keep implementation progress and failed experiments out of this file.

## Supported boundary

The initial plugin targets the current Windows Steam Build 42 stable family (Steam app `108600`). At the start of this plugin work on 2026-09-12, the official stable release was 42.20.4. The first structured script schema references are the 42.20.x PZ API Docs, so Lexeditor fails closed instead of assuming undocumented fields or layouts.

The installed Steam directory is source/runtime material and is not an editor-save destination. Authoring happens in a separate mod project. Local acceptance deployment uses Project Zomboid's native user mod directory rather than rewriting installed game files.

## Build 42 mod layout

Build 42 mods are version-aware. Lexeditor models a project with `common/` plus a `42/` version folder. The version folder carries its `mod.info` beside `media/` content. Local test deployment copies the complete project under the user's `Zomboid/mods/<project>/` folder.

Project Zomboid itself owns activation and ordering. `mod.info` exposes dependency/order metadata including `require`, `incompatible`, `loadModAfter` and `loadModBefore`. Lexeditor does not invent a second runtime loader or claim semantic merge behavior between independent mods.

## `mod.info`

The first editor models scalar fields documented for Build 42, including `name`, `id`, `author`, `modversion`, `description`, `icon`, `url`, `versionMin`, `versionMax`, dependency/order fields, and `category`.

Unknown keys, repeated non-edited keys, comments and other unmodeled lines must be preserved. A write is rejected if the file hash changed after it was read. `name` and `id` are treated as required for Lexeditor-created projects. Version bounds use explicit build-major forms such as `42.20` or `42.20.4`.

## ZedScript structure

Current Build 42 script files place authorable records under a top-level `module` block. Lexeditor's structural inventory recognizes top-level records for `item`, `recipe`, `evolvedrecipe`, `fixing`, `vehicle`, `template`, `model`, `sound`, `animation`, and `mannequin` while deliberately ignoring similarly shaped text inside comments, quoted strings, and nested component blocks.

Recognition is not the same as editability. The broader families remain read-only until their current Build 42 fields and mutation rules are grounded independently. This lets the Data Map and research tooling report real project coverage without pretending unknown record schemas are safe to rewrite.

## ZedScript item blocks

Build 42 items use required `ItemType` values from this finite set:

- `base:alarmclock`
- `base:alarmclockclothing`
- `base:animal`
- `base:clothing`
- `base:container`
- `base:drainable`
- `base:food`
- `base:key`
- `base:literature`
- `base:map`
- `base:moveable`
- `base:normal`
- `base:radio`
- `base:weapon`
- `base:weaponpart`

The first item writer edits only existing top-level scalar properties that are firmly documented and can be patched without rebuilding the block: `ItemType`, `Weight`, `Icon`, and `DisplayCategory`. `Weight` is a float with a documented minimum of `0.0`. `Icon` names resolve to item textures under `media/textures/` according to Project Zomboid's item-icon conventions. `DisplayCategory` is a translation-backed inventory category.

Nested `component` blocks and unknown item properties are preserved. Comments and quoted strings are ignored when locating structural braces. If an edited property is duplicated or missing, the first writer refuses the change rather than guessing where to insert/resolve it.

## Filesystem portability

Project APIs expose project-relative paths with forward slashes. On Windows the same file can be surfaced through case-insensitive or alias-equivalent filesystem spellings, so script discovery resolves paths and compares normalized filesystem identities before authorizing a save. Linux remains case-sensitive. The cross-platform CI matrix exists specifically to keep this containment behavior honest.

## Deployment safety

Lexeditor stages a full local-mod copy before replacing an existing Lexeditor-owned deployment. The project records hashes of every deployed file. Redeploy/remove is allowed only while the target still exactly matches the recorded deployment. An unowned folder or any external modification causes a refusal instead of overwrite/removal.

Symlinks are refused in this first deployment path, and Lexeditor state/temp files are not copied into the game-visible mod.

## Research references

- Official Project Zomboid release/status pages — current stable build boundary.
- PZ Wiki Modding / PZ API Docs: <https://github.com/PZ-Wiki-Modding/PZ-API-Docs>
- PZ Wiki Modding / ZedScripts: <https://github.com/PZ-Wiki-Modding/ZedScripts>
- PZ Wiki Modding / pz-scripts-data: <https://github.com/PZ-Wiki-Modding/pz-scripts-data>

These references supplied format/schema knowledge only in the first slice; no third-party parser source or schema dataset is vendored into Lexeditor.
