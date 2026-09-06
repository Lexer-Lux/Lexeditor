# Worklog: 056 Editor Reference Install Update 2026 07 12

## Editor/reference/install update (2026-07-12)

- Banking: The Old American Art 2.6 is installed in the game root as
  `Banking.asi`, `Banking.ini`, and `Banking.dat`; ASI changes require a full
  game restart. It is an unrelated installed third-party mod, not release content.
- Lexer supplied Kiddo's Hardcore Loot Economy Overhaul 2.6. Its main data
  files are the local `datasets/kiddos` read-only reference and must remain
  gitignored. Reference scopes are capability/file-aware: 1899 only supplies
  prices and `loot_table_reward.meta`; Kiddo supplies catalog/effects/carry/
  crafting, loot, matrix, loot config, and damage-cleanliness references.
- Craft recipe `<unlocks>` controls learning: empty means immediately known;
  an existing `RECIPE_*` requires that recipe state/pamphlet. Arbitrary new
  recipe states are not proven data-only and likely need an ASI to award them.
  UI must display empty unlocks as `ALWAYS KNOWN`, never as a blank.
- Loot `RewardCondition` is stored as a `ref` attribute, not element text.
  Loot `Type=Table` references form a graph across all loot-table files.
  Loot Name is an operational item/table identifier, never cosmetic text: use
  constrained pickers and reject unresolved IDs on save. Conditions also use
  known-reference selectors. Blank Min/Max means no local quantity override.
- Challenge mechanics live in vanilla-derived `goals_sp.meta` (stat sources,
  compare rules, desired amounts); rank order/rewards live in challenges_sp.meta.

