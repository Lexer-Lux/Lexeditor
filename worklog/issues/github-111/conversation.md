# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356286186 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111

Created: 2026-08-06T01:39:42Z; updated: 2026-09-05T06:55:19Z

Exact metadata: [source record](sources/issue-5356286186-53b7c90c20d93bdb643e4de32406f745da2d99379cdf2e7aeb4a1f03f0a3d983.json).

Casings, hulls, and empty bottles have icons in LEXEDITOR but not ingame.
.225 AP round still has no icon in either editor ingame.

## issue 5356286186 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111

Created: 2026-08-06T01:39:42Z; updated: 2026-09-06T12:46:22Z

Exact metadata: [source record](sources/issue-5356286186-0e819de1902ec0c211276ceb63a03ec6fadae618140e448dc7153a0babf8be59.json).

Casings, hulls, empty bottles and .225 AP ammunition need clear, appropriate artwork in the editor and game.

**Status: The latest report says the icons appear but look poor.** This is now an artwork-quality task, not simply missing images. Prepare replacement previews before asking you to approve a design.

## issue 5356286186 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111

Created: 2026-08-06T01:39:42Z; updated: 2026-09-06T13:57:38Z

Exact metadata: [source record](sources/issue-5356286186-54843dcad23a475582511f1882ac2bc92427c26bcda8480e9d9a4eaf0baef992.json).

Casings, hulls, empty bottles and .225 AP ammunition need clear, appropriate artwork in the editor and game.

**Status: The latest report says the icons appear but look poor.** This is now an artwork-quality task, not simply missing images. Prepare replacement previews before asking you to approve a design.

## comment 5550111811 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111811

Created: 2026-08-06T05:20:06Z; updated: 2026-08-06T05:20:06Z

Exact metadata: [source record](sources/comment-5550111811-b18cd1bf6ece3d7f4955ba4a63c8b47cfdde853f43ff711bb29e48ba91fc4ba0.json).

Built and installed. Test `.225 Round (AP)`, Empty Bottle, all six casing/hull families, and their satchel/pickup/crafting icons after a full restart. Empty Bottle now uses Rockstar's `GENERIC_BOTTLE`; `.22` and shotgun use vanilla icons; `.225/.307/.444` use the approved custom drawings.

## comment 5550111831 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111831

Created: 2026-08-06T06:17:10Z; updated: 2026-08-06T06:17:10Z

Exact metadata: [source record](sources/comment-5550111831-42fc4e36c7ba30a4f5c185a432441a7b674382a0f30e97479c7201eb8f41b258.json).

how bizarre. 225 AP icon: fixed.
casings: still no icons. still no acquisition log popups.
EXCEPT the shotgun hulls, which do have an icon, but it appears to be the a vanilla item icon of one of the shotgun ammo types, not the custom hull icon we made.

## comment 5550111846 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111846

Created: 2026-08-06T06:57:00Z; updated: 2026-08-06T06:57:00Z

Exact metadata: [source record](sources/comment-5550111846-077165bac4f1127c9b1590556ec654d568525575715e49d82b05d6ae87bd8aff.json).

Implementation update: found the missing acquisition-card bug—the active native-pickup branch never called the feed at all. It now posts exactly one card per collected casing and logs its dictionary/icon. Shotgun hull is restored from the temporary vanilla ammo fallback to the shipped custom LEX_CASING_SHOTGUN texture. Added a runtime dictionary existence/load probe because vfs registration alone does not prove UI reachability; source, repo, and live YTD hashes already match. Catalog XML and the combined release build pass. Keeping actionable until the corrected deferred install lands, then the new trace will settle any remaining blank custom textures.

## comment 5550111861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111861

Created: 2026-08-06T07:27:56Z; updated: 2026-08-06T07:27:56Z

Exact metadata: [source record](sources/comment-5550111861-d2c22245154b3615a589eaee84bd58d6a64585d59607dbf36d082b775f7fdd80.json).

now they're all blank, including the shotgun hull.
bottles are still good tho.

## comment 5550111873 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111873

Created: 2026-08-06T11:36:04Z; updated: 2026-08-06T11:36:04Z

Exact metadata: [source record](sources/comment-5550111873-794c4611d241e4e2566fb1feb53c867a32507d2e93b71d3029833b1b9aa63565.json).

no change.

## comment 5550111888 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111888

Created: 2026-08-06T12:25:43Z; updated: 2026-08-06T12:25:43Z

Exact metadata: [source record](sources/comment-5550111888-6ff32de5d60f00364ed802f725bb68e3c8758d9625c63895de40a4841a6000c4.json).

nothing has been changed.

## comment 5550111903 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111903

Created: 2026-08-06T13:26:59Z; updated: 2026-08-06T13:26:59Z

Exact metadata: [source record](sources/comment-5550111903-84d44218d1a0090c8915dac16126635856246a3619e9fe520e909d83ea470c4e.json).

Installed in development build F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96. Test after a full restart: collect pistol/revolver/repeater-or-rifle/shotgun casings and confirm the custom drawings render in both the acquisition card and satchel/crafting UI. Varmint should retain the visible vanilla rifle-ammo icon. If any are blank, attach GameplayTweaks.casings.log.

## comment 5550111916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111916

Created: 2026-08-06T14:18:45Z; updated: 2026-08-06T14:18:45Z

Exact metadata: [source record](sources/comment-5550111916-26b10f1471f82edc0dd704914483eb39ff92ff4b3bc6a553670a292d9a895b66.json).

I don't understand. You got the map icons working. Hell, you even got these icons working before. I remember it. What is the problem here? Why do you refuse to do it now?

## comment 5550111923 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111923

Created: 2026-08-06T14:41:55Z; updated: 2026-08-06T14:41:55Z

Exact metadata: [source record](sources/comment-5550111923-60ad3c1035de443eb682124281965945e1e3503b5cdec961c273ce48e326a133.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. After a full restart, collect pistol, revolver, repeater/rifle, and shotgun casings; confirm custom icons in acquisition cards and satchel/crafting. Varmint and Empty Bottle should retain their visible vanilla icons.

## comment 5550111930 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111930

Created: 2026-08-06T19:27:43Z; updated: 2026-08-06T19:27:43Z

Exact metadata: [source record](sources/comment-5550111930-d9b42d5c92f8dfb3f561c191fc5ae45c5cf918852cf982e4970022d0d74c5dd4.json).

this is getting ridiculous.

## comment 5550111949 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/111#issuecomment-5550111949

Created: 2026-08-09T09:12:59Z; updated: 2026-08-09T09:12:59Z

Exact metadata: [source record](sources/comment-5550111949-40df080ac21782c2954c9b69ab7a4052b7959b4dc0984d3689fdf973856d98cc.json).

good news: they exist. please remember how you did this for next time i ask you to put textures in the game.
bad news: they look awful and we'll have to fix them
