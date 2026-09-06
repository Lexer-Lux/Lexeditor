# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356327065 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/275

Created: 2026-08-12T03:44:13Z; updated: 2026-09-05T07:04:15Z

Exact metadata: [source record](sources/issue-5356327065-6ac9016b2800b3ddc20bab09291e7d8e113a94643787c02c52c8d6c05e7d02e8.json).

The game crashes about 20 seconds after startup in the current combined build.

The Windows dump proves a `STACK_COOKIE_CHECK_FAILURE` in `GameplayTweaks.asi`. The caller resolves to the carried-mask `itemCategory()` helper: `_ITEM_DATABASE_FILLOUT_ITEM_INFO` writes the documented five-field `ItemInfo`, but the helper supplied only two fields. The new holster transition exposed the latent overwrite; the overflow-storage page did not open or transfer inventory.

Acceptance: the helper uses the complete documented output structure, the dump-derived unsafe two-field ABI is rejected by verification, and normal startup plus the Lexer-Lux/Lexeditor#243 repair no longer crashes.

## issue 5356327065 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/275

Created: 2026-08-12T03:44:13Z; updated: 2026-09-06T13:18:34Z

Exact metadata: [source record](sources/issue-5356327065-5227d09e37124dec4216bed3ddc1244744afd34d5840ee118ded5b74f8a725e7.json).

**Status: Closed after the installed crash repair.** The mask helper supplied an undersized output buffer, corrupting the stack during item-information lookup. The buffer was enlarged and checks reject the unsafe form. This was a diagnosed overwrite, not evidence that overflow storage caused the crash.

## comment 5550160099 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/275#issuecomment-5550160099

Created: 2026-08-12T03:49:26Z; updated: 2026-08-12T03:49:26Z

Exact metadata: [source record](sources/comment-5550160099-1057dfce4f86747329527cffbdc4c1740739b62f84249e9e764f2dd4c76229da.json).

The dump identified the exact corruption: the carried-mask category helper gave `ITEMDATABASE_FILLOUT_ITEM_INFO` only two 64-bit output slots. The native writes at least six slots, so it overwrote the stack and triggered the `ERROR:FFFFFFFF` fast-fail. The buffer is now eight slots, and verification rejects the unsafe form.

The corrected development build is installed. Please relaunch normally. The Lexer-Lux/Lexeditor#243 holster repair will run after its 15-second safe window; startup must remain stable through that point before this is accepted.
