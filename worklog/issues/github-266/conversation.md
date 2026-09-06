# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356324367 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/266

Created: 2026-08-11T02:10:23Z; updated: 2026-09-05T07:03:46Z

Exact metadata: [source record](sources/issue-5356324367-f69d550baccbd09d404f353fe13697d001e42d957d4ee13697c7597fb238bece.json).

Okay so you got rid of the massively strict clamp range on the camera X. But not the distance. Come on.

## issue 5356324367 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/266

Created: 2026-08-11T02:10:23Z; updated: 2026-09-06T13:18:27Z

Exact metadata: [source record](sources/issue-5356324367-8a72e9785abdf54d0924e322271c5f69ca91bcbd668b2635723e5e19318e6bd0.json).

**Status: Closed after the installed clamp removal.** Finite horizontal and distance values are no longer stopped by the mod’s former narrow bounds. A rendered camera stopping while its value still changes is a separate game-side limit, not proof that arbitrary offsets work.

## comment 5550156275 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/266#issuecomment-5550156275

Created: 2026-08-20T10:08:23Z; updated: 2026-08-20T10:08:23Z

Exact metadata: [source record](sources/comment-5550156275-3d3537c9925c796f1e5f6c5d08443df1125decc2aa7aea5aff040fd1491ca7e7.json).

There are still clamps. Specifically on the horizontals and distance.

## comment 5550156322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/266#issuecomment-5550156322

Created: 2026-08-20T11:19:25Z; updated: 2026-08-20T11:19:25Z

Exact metadata: [source record](sources/comment-5550156322-4fa9511d7801f8c0e9dfaf6e77d50fea05b1d54efccd9e2b956d8ab9d7a3092d.json).

Installed repair: the mod no longer clamps finite horizontal or distance camera values. Test both directions past the former zero and -2 stops, then save and reload. If the displayed value keeps changing but the rendered camera stops, report that exact point because it is then a Rockstar-side limit.
