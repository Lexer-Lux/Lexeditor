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
- **Strings** — parsed PC `.strtbl` localization entries. The editor is
  language-first: every logical language slot has its own flagged subtab and
  searches across all prepared STRTBL resources for that language. Shared
  physical language blocks remain one underlying write. Only displayed UTF-16
  text is editable; identifier bytes, hashes, glyph metrics, layout metadata,
  padding, and `_ps3.strtbl` duplicates remain structural/read-only.
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
copies. Lexeditor's shared helper-version panel reports local presence, the
v1.3.10 pin, and newer upstream release metadata, but exposes no install or
automatic-update action. MagicRDR's repository declares no redistribution
license, so the checked-in bridge usage constraints are documented in
`tools/magic-rdr/README.md`.

Preparation currently covers the tuning archive, inventory/content data needed
by structured screens, PC string tables, and packed/unpacked Gringo resources.
Source archives are hashed and treated as read-only.

Saving never modifies the prepared cache or the installed `game/*.rpf` files.
Archive-backed edits are written below the project `mod` tree and **Deploy
Project** rebuilds verified copies only of affected archives under RedHook's
`update/game` override folder. Project INI/JSON runtime files remain in the
project workspace.

## External mod compatibility

Lexeditor does not treat every RDR1 mod as one stack. RedHook `.red` plugins are
separate game-root files and Lexeditor leaves them alone. Archive replacement
mods use a different namespace: Ultimate ASI Loader can overload, for example,
`update/game/content.rpf`, which is also where Lexeditor deploys its rebuilt
content archive. Only one file can own that exact path, so Lexeditor does not
claim semantic composition with another whole-`content.rpf` mod and refuses to
overwrite a deployed archive that changed outside Lexeditor.

Community patch loaders that use `patch0.rpf`, `patch1.rpf`, and similar files
are separate third-party systems. Lexeditor neither imports nor reorders those
patches and does not claim their load-order semantics as its own.

## First-time runtime setup

RedHook is an external prerequisite for using the delivered overrides in-game.
Its author permissions prohibit re-uploading the runtime, so Lexeditor does not
bundle it. Lexeditor reports exactly which RedHook files are missing and exposes
a user-initiated link to the official Nexus Mods page; it does not silently
install or update RedHook. When RedHook is already installed, the existing
`SkipIntroLogos` setting can be configured with a backup-preserving edit.

Source tests, synthetic round trips, rendered browser evidence, an isolated
candidate, and real-game acceptance are tracked separately. Passing source or
browser checks does not by itself establish that an edit has changed gameplay.
