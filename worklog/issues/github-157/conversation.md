# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356297223 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/157

Created: 2026-08-06T02:40:08Z; updated: 2026-09-05T06:57:57Z

Exact metadata: [source record](sources/issue-5356297223-b5112b4a768d0d79d1a8ce76232ff6f6dd409220fc193dfa720a74990655bef2.json).

Stuff like ammo doesn't appear in the satchel. Why not?

## issue 5356297223 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/157

Created: 2026-08-06T02:40:08Z; updated: 2026-09-06T12:54:27Z

Exact metadata: [source record](sources/issue-5356297223-65ea1f89f34b09958c84786c3ba618248d7e761f32b3284e262f97dc55de0ce3.json).

**Status: Research only.** Ammunition uses weapon-ammo storage rather than ordinary provision stacks; changing a catalog category alone does not guarantee a valid satchel row.

Audit the reported omissions and prepare a truthful display approach that preserves the real quantities. No new satchel view is ready to test.

## issue 5356297223 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/157

Created: 2026-08-06T02:40:08Z; updated: 2026-09-06T13:54:00Z

Exact metadata: [source record](sources/issue-5356297223-9a0d4d5e3de59c55cac91d522300de7605b6de271df1a05e43d0b9b0f8e8cad1.json).

**Status: Research only.** Ammunition uses weapon-ammo storage rather than ordinary provision stacks; changing a catalog category alone does not guarantee a valid satchel row.

Audit the reported omissions and prepare a truthful display approach that preserves the real quantities. No new satchel view is ready to test.

## comment 5550125035 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/157#issuecomment-5550125035

Created: 2026-08-06T03:56:49Z; updated: 2026-08-06T03:56:49Z

Exact metadata: [source record](sources/comment-5550125035-c48132dc1439040d37a0f5f29211eea6439b498b7c833e25273a36d83151e063.json).

Research result: “not in the satchel” is not one missing flag. Rockstar's satchel handler has explicit AMMO code, but live ammunition is stored and queried as ped/weapon ammo while provisions are inventory stacks; authored categories and contexts decide which representations become rows. Before changing catalog categories, audit each omission against catalog category, inventory-record presence, ped-ammo backing, and whether vanilla emits a row. Then add display-only rows or a dedicated view without corrupting quantity storage.
