# Lexeditor RDR1 plugin

This managed plugin targets the PC release of **Red Dead Redemption** (Steam app
2668510). It uses the shared Lexeditor shell and Table+Detail controls while
keeping the installed game archives read-only.

## Supported editing surfaces

- **Items** — existing inventory XML records. Lexeditor edits only direct scalar
  child fields; nested structures and record creation/deletion remain unsupported.
- **Shops** — verified `ShopInventory` records from RSC85/WGD resources.
  Price modifier, purchase quantity, and available stock are editable; other
  Gringo components are preserved.
- **Strings** — parsed PC `.strtbl` localization entries. Only displayed UTF-16
  text is editable. Identifier bytes, hashes, glyph metrics, layout metadata,
  shared language blocks, padding, and `_ps3.strtbl` duplicates remain
  structural/read-only.
- **Loot Tables** — the schema-versioned `LexerRDR.loot.json` runtime override,
  plus the exact verified item-enum call sites in
  `lootcorpsegenericnoanim.wsc`. Other WSC bytecode is not presented as editable.
- **Missions** — cash, fame, and honor reward overrides for the resolved Story
  mission table. Mission identity and extracted base evidence stay read-only.
- **Tweaks** — supported `LexerRDR.ini` values that the LexerRDR runtime
  implements.

The **Data Map** remains the authoritative per-file coverage view. Indexed files
without a verified format-specific editor stay `not-integrated`; prepared data
is not promoted merely because Lexeditor can read its bytes.

## Preparation and writes

The pinned local MagicRDR bridge reads RPF6 archives and prepares private cache
copies. The bridge is pinned; the plugin does not silently update or download it.
MagicRDR's repository declares no redistribution license, so the checked-in
bridge usage constraints are documented in `tools/magic-rdr/README.md`.

Preparation currently covers the tuning archive, inventory/content data needed
by structured screens, PC string tables, and packed/unpacked Gringo resources.
Source archives are hashed and treated as read-only.

Saving never modifies the prepared cache or the installed `game/*.rpf` files.
Archive-backed edits are written below the project `mod` tree and **Deploy
Project** rebuilds verified copies only of affected archives under RedHook's
`update/game` override folder. Project INI/JSON runtime files remain in the
project workspace.

## First-time runtime setup

RedHook is an external prerequisite for using the delivered overrides in-game.
Lexeditor reports exactly which RedHook files are missing and exposes a
user-initiated link to the official download page; it does not silently install
or update RedHook. When RedHook is already installed, the existing
`SkipIntroLogos` setting can be configured with a backup-preserving edit.

Source tests, synthetic round trips, rendered browser evidence, an isolated
candidate, and real-game acceptance are tracked separately. Passing source or
browser checks does not by itself establish that an edit has changed gameplay.
