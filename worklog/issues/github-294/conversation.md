# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356332913 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/294

Created: 2026-08-20T11:47:22Z; updated: 2026-09-05T10:48:24Z

Exact metadata: [source record](sources/issue-5356332913-3e760e2012c7d7097b0d45ba560f53bf4ed997b1e426c421bee65ee724f1c6dd.json).

Deferred visual follow-up to Lexer-Lux/Lexeditor#293.

The neutral-human Recon tag currently uses Rockstar's `blip_ambient_npc`, which is only a plain circle/ring. That design is rejected. The suggested resident substitutions—eyewitness eye for neutral humans, companion for allies, and bounty-target skull for enemies—are also rejected as an overall solution.

Later work must find or create a stronger human glyph that reads clearly as a person at the tag's smallest and largest displayed sizes. It must remain visually distinct from allies, enemies, animals, the owned horse, and plants. Do not repurpose witness, law, player-direction, companion, or bounty semantics merely because those textures already exist.

Acceptance:
- Neutral humans use a distinctive, readable human icon rather than a circle, dot, eye, skull, or companion marker.
- The icon remains legible inside the health ring across the full configured 2D/3D size range.
- The icon and surrounding ring remain aligned and retain the intended opacity behavior.
- The final choice is confirmed visually in game; a texture-name or static asset check is not acceptance.

This is deliberately deferred and does not change Lexer-Lux/Lexeditor#293's current geometry work.

## issue 5356332913 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/294

Created: 2026-08-20T11:47:22Z; updated: 2026-09-06T13:02:57Z

Exact metadata: [source record](sources/issue-5356332913-a96053dfbef77b6db14d6ad756a43cabf445100ca3add1d4599f23d1599df89a.json).

You selected the broad-brim hat/person icon. It is implemented; there is no outstanding icon-design question.

- [ ] Restart RDR2. Tag a neutral person without binoculars while #357 remains open; confirm the chosen person glyph appears, not the old plain circle.
- [ ] Change distance and available tag size/fade settings. Confirm the hat and shoulders stay centered inside the health ring; send a screenshot of any mismatch.

## issue 5356332913 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/294

Created: 2026-08-20T11:47:22Z; updated: 2026-09-06T13:02:57Z

Exact metadata: [source record](sources/issue-5356332913-e780d6d4843a46ab90d130cfc838bbcd0baf2199605d72b12e33a4b96b1b846a.json).

You selected the broad-brim hat/person icon. It is implemented; there is no outstanding icon-design question.

- [ ] Restart RDR2. Tag a neutral person without binoculars while #357 remains open; confirm the chosen person glyph appears, not the old plain circle.
- [ ] Change distance and available tag size/fade settings. Confirm the hat and shoulders stay centered inside the health ring; send a screenshot of any mismatch.

## comment 5551264293 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/294#issuecomment-5551264293

Created: 2026-09-05T10:48:23Z; updated: 2026-09-05T10:48:23Z

Exact metadata: [source record](sources/comment-5551264293-65b726f80534177e9951b4875506d2f2e9022bcc35ef038be6ca7c3c434ec5b9.json).

Selected D: the person wearing a broad-brim hat. Neutral-human Recon tags now use this icon. The existing 2D/3D sizing and opacity settings are unchanged.

In game, tag a neutral person and check that the hat and shoulders stay centered inside the health ring as the tag changes size and fades.

