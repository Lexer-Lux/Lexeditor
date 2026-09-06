# LEXEDITOR UI rules

- Top navigation is alphabetical: AI, Challenges, Crime & Law, Crafting, Data
  Map, Effects, Items, Loot Tables, Shops, Weapons. Independent subtabs are
  alphabetical; paired workflow modes retain workflow order.
- Every meaningful tabular column uses the shared sortable header. Lists
  default to Name A-Z. Intrinsically ordered challenge ranks are exempt.
- Shops uses paired `SELLS`/`BUYS` modes. After selecting one item, show its
  global catalog fields once above a three-column Shop / Requirements / toggle
  matrix. `SELLS` edits shop stock. `BUYS` exposes global sellability through
  `SELL_SHOP_DEFAULT` plus explicit PDATA exceptions; unchecked PDATA entries
  must never be presented as merchant rejection because ordinary acceptance is
  determined by compiled shop category rules. Never repeat a global price per
  shop or replace the matrix with an add dialog.
- Every tab has one toolbar `?` controlling at most one help panel. Never add a
  permanently visible explanatory box.
- Preserve focus, filters, history, and scroll across rerenders/navigation.
- Never rerender the Items table during ordinary effect autocomplete typing.
  Datalist selection, change, or Enter commits; chip add/remove updates locally.
- Item description textareas are fixed-height and internally scrollable;
  browser-native resizing caused runaway table reflow and is disabled.
- Carry rules use one compact grid: context, help, value, then stacked Vanilla/
  reference values. `LotE 999?` sits above `+ rule`; both align with the value
  column.
- Challenge ranks render as independent rounded cards: a vertically centered
  rank number, a compact rank/goal-description header with subdued technical
  IDs, then Conditions on the left and Rewards on the right. Do not merge all
  ten ranks into one visual block or float goal IDs between controls. The
  selected strand always shows all ranks; Challenges does not need a search box.
- Category and group are real catalog fields. Never invent synthetic values for
  editor organization. Items uses editor-only All, Advert, Ammo, Clothing,
  Consumables, Document, Herbs, Horses, Provisions, Upgrades, Valuables,
  Weapons, and exhaustive Misc subtabs derived from real fields/provenance.
- HTML Boolean attributes are presence-based. Omit false/null/undefined rather
  than writing `disabled="false"`.
- LEXEDITOR must work without MyOverhaul or GameplayTweaks. Optional tabs and
  integrations report unavailable gracefully.
- The server reloads cached XML when its on-disk timestamp changes. External
  project edits must never be overwritten by a later save from a stale cache.


