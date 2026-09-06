# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356310568 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213

Created: 2026-08-06T08:36:23Z; updated: 2026-09-05T07:00:52Z

Exact metadata: [source record](sources/issue-5356310568-6ac8362e9ab1e7f5a87f301c8b93120c7bff6f698e7b54f993d5051a8740fbe9.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/2e82b3ff-6ede-42c4-a6f1-9c6f9e8d7e9f" />

unless a bunch of these icons are supposed to be located outside the game world, then something's gone wrong.
notable is that they're only going outside of the game world in this point, to the southwest of the map. might say something about your location conversion algo?

## issue 5356310568 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213

Created: 2026-08-06T08:36:23Z; updated: 2026-09-06T13:31:28Z

Exact metadata: [source record](sources/issue-5356310568-6fe70abfb80f5b59439506916e7a44e1a1645b64725ecb022a1ec51ec7696dd1.json).

**Closed after the coordinate correction.** Exact source coordinates and calibrated placements replaced the erroneous southwest conversion. Individual location checks continue in #274; this does not certify every collectible.

[Original screenshot](https://github.com/user-attachments/assets/2e82b3ff-6ede-42c4-a6f1-9c6f9e8d7e9f).

## comment 5550139582 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213#issuecomment-5550139582

Created: 2026-08-06T10:52:37Z; updated: 2026-08-06T10:52:37Z

Exact metadata: [source record](sources/comment-5550139582-1640b30dac2b1fdf11cfcbadd8864d0897fe5ac2576960caba3a3e8817dfe751.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/9f42b0ab-2c76-4a6a-a870-b2b392dc3cd2" />
somewhat better but there are still out of bounds icons, which indicates your coordinates formula is still messed up.
surely there must be some better way of doing this than trial and error.

## comment 5550139593 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213#issuecomment-5550139593

Created: 2026-08-06T11:08:57Z; updated: 2026-08-06T11:08:57Z

Exact metadata: [source record](sources/comment-5550139593-f4a3656df42f820f87061d92b9431eb4a6904a9c9d0f54afab5f4f43a49a5362.json).

you did literally nothing.
moreover, i'm just now noticing that you didn't actually fix your formula for mapping the points you downloaded onto the map. you just manually moved a few of the icons that were far outside the playable zone. everything else is the exact same.

## comment 5550139608 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213#issuecomment-5550139608

Created: 2026-08-06T12:08:03Z; updated: 2026-08-06T12:08:03Z

Exact metadata: [source record](sources/comment-5550139608-74a24e135bfc38d9286c7f81e47c1131afd63ce7db7e8ce7767d45fee45c1546.json).

The manual-outlier approach was removed. The installed CSV is now deterministically rebuilt from RDOMap's checked-in converter and authored coordinates; 268 bone, dreamcatcher, exotic, carving, and grave pins match exactly, and a second rebuild changes zero rows. Installed for the next restart with the current payload and moved to 	est me; this is a test candidate, not an in-game success claim.

## comment 5550139618 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213#issuecomment-5550139618

Created: 2026-08-06T12:41:19Z; updated: 2026-08-06T12:41:19Z

Exact metadata: [source record](sources/comment-5550139618-f139deb2105e7ce09f4a712848a786a175885f7d1ae1994d43fbc59afe0e6be9.json).

<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/551d4fbe-fb03-42bb-8ab7-f356c4911dd7" />
it's still bad. just in a different way.

## comment 5550139637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/213#issuecomment-5550139637

Created: 2026-08-06T13:27:17Z; updated: 2026-08-06T13:27:17Z

Exact metadata: [source record](sources/comment-5550139637-0d240939ebad6382cd36a836370e796de0ec1a832d7520e7beef56caadf71ca5.json).

Installed in development build F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96. The dataset now contains 268 exact source coordinates plus 166 independently calibrated non-card/non-hideout pins. Open the pause map and inspect the previously displaced southern/western examples: Jesuit Missionary, Riley's Charge, Two Crows, Donkey Lady, and Sperm Whale Bones. Confirm their icons sit on the actual locations and that no collectible category disappeared.
