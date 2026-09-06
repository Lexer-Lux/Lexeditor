# Worklog: 046 Key Technical Knowledge

## Key technical knowledge

- Data files are text XML loaded via LML file replacement. Prices in
  `catalog_sp.ymt` are **cents** (`acquirecosts`/`sellprices`); consumable
  effects in its `effectsids` section (`percent` = core refill). Loot:
- Consumable-description terminology: Health Core means hunger, Stamina Core
  means thirst, and Dead Eye Core means wakefulness; the same applies to horse
  cores. Do not call a core refill health/stamina/Dead Eye restoration. Reserve
  those words for outer-bar effects, and mention horse benefits when present.
- Consumable descriptions should remain varied, natural prose. Only the
  magnitude word for a mechanical effect is standardized to Lexer's selected
  scale; never turn every entry into a formulaic stat sentence. The canonical
  scale is 6.25%=marginal/marginally, 12.5%=slight/slightly,
  25%=modest/modestly, 37.5%=moderate/moderately,
  50%=considerable/considerably, 62.5%=substantial/substantially,
  75%=great/greatly, and 100%=complete/completely.
- When authoring consecutive item descriptions, vary sentence openings and
  syntactic structure; do not fall into repeated "A/An [item]..." starts.
- Consumable-description iteration rules: read the current raw catalog record
  before drafting, never a stale/cached label; describe every immediate
  player/horse core or outer-bar effect, while treating Calories as optional
  flavor rather than a duplicate immediate hunger effect; use the exact
  canonical tier word matching each percentage; translate core effects as
  hunger/thirst/wakefulness and outer-bar effects as Health/Stamina/Dead Eye;
  phrase penalties naturally (for example, "leaves you marginally thirstier");
  keep each entry to one or two compact sentences; add one concrete,
  item-specific sensory/use detail; and avoid stiff, template-like wording,
  repeated openings, or unsupported lore.
  `loot_table_*.meta` (`Rate` 0–1, Type Table|Item), `loot_items_matrix.meta`
  (skinning). Challenges: `challenges_sp.meta`
  (`update:/common/data/stats_and_challenges/`); money rewards were
  `CScriptReward` + `CHALLENGE_REWARD_TYPE_MONEY_*` (54 stripped).
- Catalog items expose `ui/key` (in-game name) and `ui/description` (in-game
  description), both backed by localization strings. LEXEDITOR must expose
  both as real editable game text. Some records, including the Pig Mask, omit
  `ui/description`; editing one creates `<ITEM_KEY>_DESC`, attaches it to the
  catalog record, and writes its text through `strings.gxt2`.
- LML does not discover a loose `strings.gxt2` automatically: the mod's
  `install.xml` must include it as its own `<Resource><DataFile>strings.gxt2`
  entry. This mapping was missing until 2026-07-15, so editor localization
  edits existed on disk but RDR2 continued showing vanilla text. LEXEDITOR's
  localization save path now repairs a missing mapping automatically. Text
  database changes require a full RDR2 restart.
- LEXEDITOR can create new catalog effect records. New records may choose a
  new symbolic catalog-reference label/hash and new magnitude/timing values,
  but must reuse an existing engine Behavior ID; data cannot invent a new
  engine operation. Both effect-reference hashes and Behavior IDs support
  separate editor-only labels in `editor/labels.json`. Effects uses the same
  single toolbar `?` help toggle as every other tab and must not render a
  permanently visible explanatory box.
- Effects now has two shared-style subtabs: `Effects` edits effect records and
  selects their real engine Behavior ID from a dropdown; `Behavior IDs` lists
  each distinct reusable engine ID, its editor-only label, and usage count.
  Behavior labels remain in `editor/labels.json`, while changing an effect's
  selection writes that record's actual `<id>` in `catalog_sp.ymt`. The server
  rejects invented IDs and accepts only behaviors already represented by the
  loaded catalog. Do not replace the effect-row selector with a behavior-label
  text field again.
- Custom effect identity uses two separate editor metadata scopes: the stable
  symbolic catalog identity (`effectSymbols`, convention `LEX_EFFECT_*`) and
  the readable editor label (`effects`). On 2026-07-15 all 24 user-created
  pre-existing effects and their 38 item references were rehashed to the
  `LEX_EFFECT_*` namespace; `MINISCULE` was corrected to `MINUSCULE`. Do not
  conflate or overwrite the symbolic ID when changing a readable label.
- LEXEDITOR's optional Settings tab edits `GameplayTweaks/GameplayTweaks.ini`
  through `/api/settings`; it preserves INI comments and uses toggles for
  Boolean settings. The tab reports unavailable rather than failing when a
  public LEXEDITOR user has no GameplayTweaks installation. On Lexer's machine
  the game-root `GameplayTweaks.ini` is a hard link to the project source, so
  editor saves are exactly what the ASI hot-reloads every ~2 seconds.
- Natives: latest DB in `_downloads/natives.json`
  (query: `python _downloads/grep_natives.py PATTERN`). Gems:
  `_GET_ATTRIBUTE_CORE_VALUE(ped, 0|1|2)` → 0..100;
  `ANIMPOSTFX_SET_STRENGTH(name, 0..1)` = 0xCAB4DD2D5B2B7246 (call after PLAY);
  animpostfx names in femga/rdr3_discoveries (e.g. `PlayerRPGEmptyCoreHealth`).
  AnimPostFX stack (several at once); timecycle modifiers do NOT (one global).
- Vanilla extraction (done 2026-07-06 with **OpenIV 4.1**, installed at
  %LocalAppData%\New Technology Studio\Apps\OpenIV): raw dumps live in
  `_downloads\extract\` (common_0_data, update_1_common, catalog_vanilla).
  Mount map (from appdata0_update.rpf/mountmanifest_tu.xml): `platform:` =
  data_0.rpf (catalog_sp.rpf is at data/itemdatabase inside it), `common:` =
  common_0.rpf, `update:/common` = update_1.rpf/common. OpenIV can't be used
  while the game is running.
- OpenIV exports PSO .ymt with joaat-hashed names (`UNK_MEMBER_0x…` tags,
  hashed key attributes AND hashed string texts). De-hash by building a
  joaat(lowercase) dictionary from Kiddo's resolved file — scripts:
  `_downloads\dehash_catalog.py`, `dehash_attrs.py`, `rebase_catalog.py`,
  `make_novignette.py`. OpenIV and CodeX display unknown fields under
  DIFFERENT hashes (e.g. 0x8F555A17 ↔ Kiddo/CodeX's UNK_MEMBER_0x093520C7 —
  same per-item field); map by structural position, and keep Kiddo/CodeX
  naming since that's what LML accepts.
- Ambient vignette = `postfx_vignette_intensity` in timecycle weather presets
  (`w_*.xml` etc.); gameplay-FX vignettes live in `timecycle_mods_*.xml`
  (never zero those).
- The GitHub repo for this project is **private**.
- LEXEDITOR table behavior is global: every meaningful data column in every
  tabular view must use the shared click-to-sort header (first click ascending,
  second descending, with a direction indicator). Do not wait for Lexer to
  request sorting separately for each new tab. Action-only columns and
  intrinsically ordered structures such as challenge ranks are exempt.
- HTML boolean attributes are presence-based: the shared `el()` helper must
  omit false/null/undefined attributes rather than writing e.g.
  `disabled="false"`, which still disables the control. This was the cause of
  the inert challenge Series/Parallel buttons.
- LEXEDITOR top-level navigation is alphabetical: AI, Challenges, Crime & Law,
  Crafting, Data Map, Effects, Items, Loot Tables, Shops, Weapons. Independent
  subtabs are also alphabetical (for example Loot and AI); paired modes with an
  inherent workflow retain that workflow. Applicable list views default to Name
  A-Z with the downward indicator; raw XML/file order is not a UI sort.
- Item `category` and `group` are real catalog fields, never editor-only
  organization. LEXEDITOR must not invent synthetic values for navigation.
  TODO #65 adds editor-only Items subtabs (All Items, Plants, Weapons,
  Documents, Ammo, Horses) derived from existing record data without rewriting
  category/group.
- Item price references are centered beneath the numeric box, independent of
  whether a search icon exists. Carry-cap rules are compact single-row units:
  context, help, and value remain left-to-right; Vanilla and Kiddo references
  sit immediately to the value's right, stacked one reference per line. `+ rule`
  remains aligned with the value column. Each number is a context contribution,
  not necessarily the final capacity after applicable rules combine.
- Challenge content is editable in `goals_sp.meta`: 138 SP goals (135
  `StatsGoal`, 3 point-to-point) expose stat/score sources, comparison logic,
  target count (`desiredGoal`), partial/overflow progression, and UI labels.
  `challenges_sp.meta` controls rank ordering/grouping and rewards. New goals
  are constrained to score-source/goal types the engine already supports.
- Challenge order has no proven Boolean field. The attempted data-only
  Series/Parallel conversion is disproven: splitting a strand into one-rank
  `StatsChallengeLinear` roots makes every root render as a duplicate entry
  under the same vanilla `menuLink`. On 2026-07-15 Bandit, Gambler, and
  Herbalist were repaired from ten roots back to one root / ten ranks, and the
  switch was removed. `StatsChallengeUnordered` exists in the type corpus but
  has no extracted vanilla instance; do not claim it works. Parallel progress
  now requires ASI-owned tracking or the planned custom Challenges UI.
- Adding another challenge root and its goals is structurally possible, but a
  tenth top-level pause-menu strand is not data-driven. On 2026-07-14 a fully
  wired minimal tenth strand (root, goal, localization, reused icon/menuLink)
  loaded without crashing, yet the in-game Challenges menu still displayed
  exactly nine strands. Treat the pause-menu list as executable-hardcoded:
  custom challenge content is supported only by repurposing the nine existing
  strand slots unless a custom UI replaces that menu. The visual half of an
  ASI-owned replacement is feasible: RDR2 Native Menu Base exposes arbitrary-
  coordinate sprite/text drawing plus keyboard/controller input, although its
  supplied widgets are only vertical menus. The seamless pause-menu half is
  still unproven: `progress_menu` is a UI app and UIAPPS natives expose current
  activity plus close/launch/transition controls, but we must first demonstrate
  that entering Challenges can be detected, suppressed without a softlock, and
  restored correctly on Back. Its renderer also defaults to draw order 0
  (behind game UI), so our implementation must close/hide the original page or
  deliberately change layering. This would be a behavioral replacement, not
  an XML extension or modification of Rockstar's compiled UI asset.
- In challenge goals, a `StatsGoalParamIntSum` can contain several independent
  score-source Items; removing one must delete its whole child Item from
  `scoreParams`. A `resetParam` desired goal is a reset window/time limit (for
  example `TOTAL_PLAYING_GAME_TIME=86400` implements "in a day"), not a second
  progress counter. `ACBAND_*`/`ACSHOT_*` strings shown near editable English
  text are localization lookup keys, not additional gameplay requirements.
- Challenge-gated shop stock is data-feasible and already used by vanilla:
  `challenges_sp.meta` awards `CUnlockReward` with the catalog item key;
  `catalog_sp.ymt` supplies that item's price and lists it under the selected
  `shopsinventories` entries. The unlock changes availability rather than
  giving the item directly, while shop membership determines which merchants
  sell it. Listing the item only in chosen shop types restricts it accordingly.
- Kiddo's no-auto-ammo-pickup mechanism is data-only: in
  `lootconfigdata.meta`, the `QuickBehavior` prompt entries with
  `TextId=TAKE_AMMO` are commented out. Enemy/honor loot uses
  `loot_table_ped.meta` + `loot_table_itemgroups.meta` with
  `RewardCondition` refs such as `PLAYER_HAS_LOW/HIGH/NEUTRAL_HONOR`;
  money ranges/tables live in `loot_table_reward.meta`.

