# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356300897 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175

Created: 2026-08-06T03:27:51Z; updated: 2026-09-05T06:58:50Z

Exact metadata: [source record](sources/issue-5356300897-b6c93975d1f654b099dc2db01fd81b0fe4a98319c4b09c85c5c0f1f71e1c8471.json).

(No body was present in this captured version.)

## issue 5356300897 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175

Created: 2026-08-06T03:27:51Z; updated: 2026-09-06T13:17:21Z

Exact metadata: [source record](sources/issue-5356300897-bf7d7b0b290ac129e2dd07b6a799b76ebf4718173aba256f166bcc22fca23ddc.json).

**Status: Closed after the installed mask-carrier recovery.** The selected mask can recover after its inventory carrier disappears, without requiring another wardrobe visit. Equipping/removing it should keep its wheel check mark synchronized and preserve shops and horse inventory interactions.

## comment 5550129211 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129211

Created: 2026-08-06T05:52:43Z; updated: 2026-08-06T05:52:43Z

Exact metadata: [source record](sources/comment-5550129211-c4933731c827530beb900a4f960d32f44b85e99663ec68f765cf93a7478cecfe.json).

Integrated the command/scan handshake so mask OFF keeps the carrier unchecked until Rockstar's worn-component state actually catches up, rather than re-arming from stale scan data. Combined ASI build passes; installation is queued for RDR2 exit, so this remains actionable until it lands.

## comment 5550129224 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129224

Created: 2026-08-06T08:59:01Z; updated: 2026-08-06T08:59:01Z

Exact metadata: [source record](sources/comment-5550129224-a622ca80714bc6a5578883a09cbbc2f6380c3f5bd2816567a26ca1cde31ff824.json).

The requested-state mask latch fix is integrated and installed in `C92A04F…CCA3`. Moved to `test me` for wear/remove/check-mark verification.

## comment 5550129239 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129239

Created: 2026-08-06T12:01:17Z; updated: 2026-08-06T12:01:17Z

Exact metadata: [source record](sources/comment-5550129239-f040643914a758f22b19eebd499c1285aa1467522379e0170ce0f52e7fd75260.json).

still not fixed.

## comment 5550129249 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129249

Created: 2026-08-06T12:59:07Z; updated: 2026-08-06T12:59:07Z

Exact metadata: [source record](sources/comment-5550129249-7fd6c101feb7adef79df2d7179636a4f9885a654ab947853c1c4bafbdb5c8070.json).

still not fixed.

## comment 5550129258 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129258

Created: 2026-08-06T14:42:12Z; updated: 2026-08-06T14:42:12Z

Exact metadata: [source record](sources/comment-5550129258-a5077291273aae931a9086e3e5615f1b0d70dfedb51e86baf587a1d75439f7ca.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Equip and remove a carried mask; confirm the radial check mark refreshes immediately in both directions.

## comment 5550129267 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129267

Created: 2026-08-06T16:51:57Z; updated: 2026-08-06T16:51:57Z

Exact metadata: [source record](sources/comment-5550129267-075d6ac7cdbef42fd6da36880b3ddf208792c8f0d29dbb4c6362ecd230eef439.json).

Still not fixed.

## comment 5550129280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129280

Created: 2026-08-06T18:14:52Z; updated: 2026-08-06T18:14:52Z

Exact metadata: [source record](sources/comment-5550129280-4708da4a17055d9f593e1a236c392fbf171c68b8304013fef07d77461bd8cdb5.json).

Now selecting the mask from the radial menu makes me do the animation but the mask never actually goes on. Nor does the check mark appear. The whole thing has been broken.

## comment 5550129287 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129287

Created: 2026-08-06T18:21:06Z; updated: 2026-08-06T18:21:06Z

Exact metadata: [source record](sources/comment-5550129287-f05e5da985f2e161b7becd4ae04ca4e4bf4ea17e058e41e305885977b99c6e7f.json).

The earlier horse-wheel guard covered carried-mask synchronization but left shared ammo-cap maintenance running. This crash occurred while the horse weapon page was committing a rifle selection; the direct ammo selector did not fire, and the carried-mask log confirms its guard was active. `updateSharedAmmoCaps` was still calling `SET_MAX_AMMO_OVERRIDE` for enabled ammo families every 250 ms during Rockstar's live equip transaction.

The wheel-and-settle guard now covers carried-mask synchronization and all shared ammo/item-cap maintenance. The corrected ASI is installed and hash-verified:

`B91987788C09D508BAEFB88E0E0223D8B599EF7785B169B963E6F38F0573B271`

Runtime check remaining: retrieve/change horse weapons repeatedly and confirm the wheel closes and equips without ERROR:FFFFFFFF.

## comment 5550129302 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129302

Created: 2026-08-09T09:10:45Z; updated: 2026-08-09T09:10:45Z

Exact metadata: [source record](sources/comment-5550129302-69fcaec72f4cfcb79446757da878cf1ffae20c77c97c7b307a7386fbd7867d03.json).

now i can equip masks again but now we're back to no check mark on the radial when it's equipped.
this is getting ridiculous. it's two steps forward and two steps back.

## comment 5550129313 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129313

Created: 2026-08-09T11:07:13Z; updated: 2026-08-09T11:07:13Z

Exact metadata: [source record](sources/comment-5550129313-a880bf4fa655a3613f701d2ba837d31cc6e3c0dd5312e4abe16561b27261175c.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53. The mask proxy now writes the carrier clothing-active state and refresh bits immediately when the real mask interaction is commanded, removing the two-second stale checkmark window. Test wheel checkmark, equip/unequip, wardrobe change, and horse weapon retrieval.

## comment 5550129322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129322

Created: 2026-08-10T05:33:26Z; updated: 2026-08-10T05:33:26Z

Exact metadata: [source record](sources/comment-5550129322-e72c7805c7387674031e7f8fcf4734c450e3a3c66fbbb26c4a5e4d84c57b2d99.json).

Now the check appears when I put it on and doesn't go away when I take it off.
This is getting ridiculous. We've been here like twice before already. We're just wasting time and going in circles.

## comment 5550129332 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129332

Created: 2026-08-10T07:16:53Z; updated: 2026-08-10T07:16:53Z

Exact metadata: [source record](sources/comment-5550129332-bc78f4c331b95dfa474454340ca60a72125207b7583376b1e989b17750502823.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test carried-mask check mark selection and persistence without oscillation.

## comment 5550129339 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129339

Created: 2026-08-10T08:00:33Z; updated: 2026-08-10T08:00:33Z

Exact metadata: [source record](sources/comment-5550129339-8f97a5292d78b96bc2ac5a1e96842d5e14d78321ce78b066ad50e55cd82ebfae.json).

OMFG YOU DID IT!!!!!! SO PROUD OF U

## comment 5550129353 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129353

Created: 2026-08-16T06:36:49Z; updated: 2026-08-16T06:36:49Z

Exact metadata: [source record](sources/comment-5550129353-2892100d23baff3125f1c09fc888527ac38e7710ca5e3b3963cd63743b68b57a.json).

This regression is confirmed. The wheel mapping still exists, but the live trace shows the selected Psycho-mask proxy has no inventory count or clothing GUID. Its add path was limited to a new selection edge, so after the carrier disappeared the unchanged configured mask could never recreate it—even when the same mask was selected again at camp. Lexer-Lux/Lexeditor#175 is reopened and actionable. I built a bounded recovery that waits for shops, inventory transactions, item interactions, and the wheel to be idle, then requires positive count and clothing-GUID readback. Installation is queued for the current RDR2 session to close.

## comment 5550129378 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/175#issuecomment-5550129378

Created: 2026-08-16T06:38:39Z; updated: 2026-08-16T06:38:39Z

Exact metadata: [source record](sources/comment-5550129378-c4b5ba7fe6c64f99c1d0a9fb48ff3e6198492df2c25337384a8e02992b38d47a.json).

The fix is installed. On the next full Story restart, wait a few seconds after gaining control, then open the item wheel. The selected Psycho mask should be back without another wardrobe visit. Put it on and remove it from the same segment; confirm the check mark follows both states. Then confirm a General Store prompt still works and take one weapon from your horse. Report the first failed step.
