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
- **RBF Scalars** — prepared tuning resources whose *bytes*, not filename, prove
  the `RBF0` record format. A clean-room bounded parser exposes only boolean,
  uint32, and float32 leaves. Saves patch the original fixed-width byte spans in
  place and reject stale identity; strings, vectors, byte blocks, unknown tags,
  trailing bytes, and all unedited data remain opaque and byte-preserved.
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

The compatibility model is based on public PC loader/mod packaging and synthetic
filesystem tests; it is not a claim that third-party loaders executed in this
worker environment.

- **Ultimate ASI Loader update-folder replacements.** Its public documentation
  defines `update/` as an overload-from-folder path. Public RDR1 mods including
  No War Horse, Save Anywhere Workaround, and Instant Loot Anims distribute a
  whole `update/game/content.rpf` option and/or loose files for manual MagicRDR
  merging. Lexeditor also owns `update/game/<archive>.rpf` while deployed. A
  synthetic pre-existing whole `content.rpf` collision proves Lexeditor does
  **not** silently semantic-merge that archive: it records the original,
  replaces it only while Lexeditor owns the path, restores it byte-identically,
  and refuses redeploy/revert after an external post-deploy mutation.
- **Loose archive-relative replacements.** The same synthetic deployment puts
  an inventory XML and a public-mod-shaped loose WSC into one project content
  archive and proves both replacements reach the rebuilt copy while the stock
  `game/content.rpf` hash remains unchanged. This exercises Lexeditor's own
  composition boundary; it does not prove two independently built RPF archives
  can be merged safely.
- **ASI / RedHook plugins.** Public Ultimate ASI Loader documentation supports
  root/scripts/plugins ASI loading; RDRFix is a public RDR1 ASI example. Official
  RedHook documentation says modern RedHook plugins use `.red` and its install
  example places `RedTrainer.red` in the game root. Lexeditor neither imports
  nor rewrites root `.asi`/`.red` files, and synthetic deployment proves their
  bytes remain untouched. RedHook explicitly does not officially support other
  mods, so actual `.red` coexistence remains a retail/runtime acceptance item.
- **`patchN.rpf`.** The public `rpf_patch.asi` page documents `game/patch0.rpf`,
  `patch1.rpf`, ... and says higher patch numbers override lower ones. Lexeditor
  does not import, create, reorder, or modify those files; synthetic checks prove
  existing `patch0.rpf`/`patch9.rpf` bytes survive Lexeditor deploy/revert. The
  stated priority is third-party loader documentation, not a Lexeditor runtime
  result. CodeX's public RDR1 file manager also deliberately excludes patch0..
  patch998 archives from its ordinary archive scan, so its research code is not
  independent proof of the newer PC loader's execution order.

These tests establish filesystem ownership and restoration only. They do not
establish live loader precedence between `update/game/*.rpf`, `patchN.rpf`, ASI,
or `.red` plugins.

## Data Map format audit

A public CodeX.Games.RDR1 survey was used as format evidence only; the repository
has no declared redistribution license, so its implementation is not copied.
The new RBF0 slice uses only independently reimplemented record facts and
in-place writes. Other families remain protected:

- WGD, WTL and WNM expose public readers but their file-level `Save()` paths are
  null/incomplete; WSF similarly never returns built bytes. Only the already
  verified ShopInventory WGD substructure has a bounded Lexeditor writer.
- Audio DAT has a public reader but its save/read/write methods are explicitly
  unimplemented.
- WSI/WSP/WSG/WFT/WFD/WVD/WTD have public RSC6 writers, but safe editing depends
  on broad pointer/resource-graph serialization, resource type/version flags,
  and representative PC files. No retail resources are available here to prove
  byte preservation or roundtrip compatibility, so no editor is exposed.
- Unrelated WSC bytecode remains opaque except for the already verified corpse
  loot call sites; `_ps3.strtbl` remains intentionally excluded from the PC
  editor.

A Data Map row is promoted for RBF0 only after its prepared bytes contain the
`RBF0` header, the protected parser validates the structure, and at least one
safe fixed-width scalar exists. Same-extension non-RBF files remain Not
integrated, so filename/index research alone still cannot grant editability.

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
