# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356331805 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/291

Created: 2026-08-20T10:07:20Z; updated: 2026-09-05T07:05:11Z

Exact metadata: [source record](sources/issue-5356331805-b38c8a53ac04cfdeaab476ced053ae4d054f0da4cfd64f6d7d48e5e534f03c6e.json).

oh lol. the lantern stays on when you're on your horse. real bad clipping. it should not be there in that case.
this makes me think, though -- could we put a lantern on the horse, attached to some point, and have it just follow the same light on/off logic as the player's lantern? if so, what points can we attach it to? can you make a horse lantern item in the shop where once you buy it that lantern shows up on your horse -- specifically, any horse with your saddle on it? oh, it would be attached to the saddle. convenient

## issue 5356331805 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/291

Created: 2026-08-20T10:07:20Z; updated: 2026-09-06T12:57:15Z

Exact metadata: [source record](sources/issue-5356331805-50878111050828366fc2b79898e91723065e5e8701001c811f39febfb60ee73e.json).

Hide the rider’s belt lantern while mounted and attach the purchased horse lantern to the player’s saddle horse, controlled through the radial.

**Status: An implementation is reported installed, but the purchase/equip handoff is incomplete.** Specify the exact shop/item and equipment route, and resolve relevant light-control failures before asking you to buy and test it.

## comment 5550165066 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/291#issuecomment-5550165066

Created: 2026-08-20T11:19:30Z; updated: 2026-08-20T11:19:30Z

Exact metadata: [source record](sources/comment-5550165066-b81badd5ef0bc78c5c86613e82e1a3aaf031ee1565150cc3462877f610524834.json).

Installed implementation: the player belt lantern is removed while mounted. An owned horse-lantern item now uses the player saddle horse, its authored harness, and the resolved saddle-horn attachment. Test buying and equipping it, confirm the harness follows the saddle horse, confirm no belt lantern remains on the rider, and confirm the radial toggle controls the horse light.
