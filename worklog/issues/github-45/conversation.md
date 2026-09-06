# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286792638 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/45

Created: 2026-08-29T13:29:47Z; updated: 2026-09-04T12:24:54Z

Exact metadata: [source record](sources/issue-5286792638-4676cdeb8b44bfdf367f25586dba638b236ab9e10bfe46649acf62eda259e3c5.json).

Create one shared Hoverable relationship control for every game plugin.\n\nRequested behavior:\n- When text or a control mentions a record that has its own tab, subtab, or selectable list entry, hovering it shows a visible box around the linked mention.\n- Activating the mention navigates directly to the target view and selects that record.\n- This applies across plugins and relationship types: FF8 GF compatibility links to the named GF, item references link to Items, RDR2 loot entries link to their Items record, Crafting recipe inputs and outputs link to their records, and equivalent future relationships use the same component.\n- Add a global LEXEDITOR setting named Alt + Click hoverable linking. It is disabled by default. When disabled, ordinary click follows a hoverable. When enabled, only Alt+Click follows it and ordinary click keeps the field/control behavior.\n- Keep keyboard access and an accessible target description.\n- Record the design as a global Lexeditor UI rule so new views are built with resolvable relationship links in mind.\n\nImplementation must use a shared UI component and navigation contract. Plugins only resolve game-specific target type, stable ID, tab/subtab, and selection state.

## issue 5286792638 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/45

Created: 2026-08-29T13:29:47Z; updated: 2026-09-06T13:16:46Z

Exact metadata: [source record](sources/issue-5286792638-fa49d1e68a4e5d46009dc6f583f119477f0b68219d95e0a153c92aa69699f579.json).

**Status: Closed after implementation.** Linked record mentions use one shared highlight and navigate to the matching record. The global Alt+Click option preserves ordinary field interaction when enabled; duplicate hover outlines were removed.

## comment 5462795380 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/45#issuecomment-5462795380

Created: 2026-08-29T13:53:12Z; updated: 2026-08-29T13:53:12Z

Exact metadata: [source record](sources/comment-5462795380-8e065dba843848dc2f7bf904fcdff359eb0e6cd006775cca61e2301450a158e2.json).

Implemented one shared hoverable system across the current plugins.

- FF8: GF compatibility names open the exact GF; item mentions in Items, Shops, Weapons, and item-valued controls open the exact item.
- RDR2: resolved Items, Crafting, Effects/Behaviors, Loot, Shops, Weapons/Ammo, and Mob mentions open their exact records. Broken or ambiguous references stay plain.
- Warband: both troop names in Troop Trees open and select the exact troop.
- RDR1: no links were added because its current shop and loot keys do not have a proved inventory mapping.

The global Settings screen now has **Alt + Click hoverable linking**, off by default. With it off, click follows a link. With it on, plain click keeps the current control behavior and Alt+Click follows the link. Keyboard activation remains available.

Hidden renders confirmed the hover boxes and exact destination selection in FF8, RDR2, and Warband. Please restart Lexeditor once, then try the GF Compatibility, RDR2 Loot/Crafting, and Warband Troop Trees examples.

## comment 5464105876 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/45#issuecomment-5464105876

Created: 2026-08-29T18:25:44Z; updated: 2026-08-29T18:25:44Z

Exact metadata: [source record](sources/comment-5464105876-e7f0ff8eab5cc1214d8cd6584ae4ebee197dbc9cd3da0bd05ec11011775c5b84.json).

Removed the doubled hoverable outline. Hoverables now keep one containing-box border and the light highlight, without the second inset line.
