# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356293703 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/141

Created: 2026-08-06T02:21:37Z; updated: 2026-09-05T06:57:06Z

Exact metadata: [source record](sources/issue-5356293703-acd6fb308a0ca5554ccf1211c6ea16b6c614220a4fb5405ac9ec677d30922dee.json).

 MORE GUNSMITHS — add gunsmiths to cities that don't have one, if possible.
I knew all this? OBviously I have to give them interiors and stuff. HOW DO I DO IT?????????????????

## issue 5356293703 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/141

Created: 2026-08-06T02:21:37Z; updated: 2026-09-06T13:31:14Z

Exact metadata: [source record](sources/issue-5356293703-2921996484c9879ef7d93a74b1a7bfc22526c4cbf9cff1dcc31b760e399b436e.json).

**Actionable — practical setup remains.** Your question was how to create the shop, not whether interiors are needed. Blackwater has a recognized shop ID and is the proposed first example.

The concrete interior, merchant, stock, interaction and persistence setup still needs documenting and proving. No prototype or prepared test is available; another request to approve research is unnecessary.

## comment 5550120751 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/141#issuecomment-5550120751

Created: 2026-08-06T02:34:59Z; updated: 2026-08-06T02:34:59Z

Exact metadata: [source record](sources/comment-5550120751-b2822bc5adc810e8c8ca3797ea92f3d43306d372d3af8b4436ec39fa245a7176.json).

Research result: feasible, but not as a simple catalog/data toggle.

Rockstar's Story Mode `shop_gunsmith.c` already recognizes `SHOP_BLK_GUNSMITH`, alongside the five fully shipped gunsmiths. However, the extracted persistent-character data only supplies complete owners/schedules for Valentine, Rhodes, Saint Denis, Annesburg, and Tumbleweed. A new town gunsmith therefore needs the physical shop/interior, merchant ped + persistence/schedule, shop interaction/catalog binding, blip, hours, and death/hostility recovery.

Blackwater is the best first implementation because its shop ID already exists and the public [Blackwater Gunsmith mod](https://www.nexusmods.com/reddeadredemption2/mods/2858) proves the missing world/interior portion is portable. Strawberry/Armadillo/other towns would need a selected building and a genuinely new full shop setup rather than merely enabling a dormant merchant.

Proposed implementation order: Blackwater first using the existing mod as reference; verify buying, customization, shop hours, blip, merchant persistence, robbery/hostility recovery, and save/reload; then reuse that proven path for the next selected town.
