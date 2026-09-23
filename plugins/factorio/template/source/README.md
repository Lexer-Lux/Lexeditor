# Factorio source snapshot

Lexeditor does **not** execute or rewrite source-mod Lua.

1. Start from the exact Factorio 2.1 installation/mod set you want to edit.
2. Use Factorio's documented `--dump-data` command.
3. Copy the resulting JSON prototype dump here as `data-raw-dump.json`.
4. Optionally copy that Factorio user profile's `mod-list.json` here. Lexeditor reads enabled mod names only to preserve late override load order.

The source files remain read-only. Structured edits are saved to `../overrides.json`, and **Export Mod** writes a separate native Factorio mod to `../build/`.
