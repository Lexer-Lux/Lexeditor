# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356328410 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/280

Created: 2026-08-13T01:44:54Z; updated: 2026-09-05T07:04:32Z

Exact metadata: [source record](sources/issue-5356328410-8b2d1e3311d07ea97c9ab9ce5295717bd1e57448d054c488d358fa01b91b9ee2.json).

you shouldn't keep your gun in your hand if you enter climb mode with it in your hand.
your hands should be empty. obviously....

## issue 5356328410 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/280

Created: 2026-08-13T01:44:54Z; updated: 2026-09-06T13:18:40Z

Exact metadata: [source record](sources/issue-5356328410-29801fa0cdcaa66fc668d03b77766ea808a2c9698f40e785c7d44c2f20563095.json).

**Status: Closed after installation.** Every climbing-entry path stows the held weapon so both hands are free, without deleting it. Current failures to enter or remain attached to climbing surfaces are separate in #193.

## comment 5550161659 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/280#issuecomment-5550161659

Created: 2026-08-13T02:11:45Z; updated: 2026-08-13T02:11:45Z

Exact metadata: [source record](sources/comment-5550161659-d62616324bc0094e935bbe16b6690d19872d15e7ccc0cf75de640d9430f60a13.json).

Implemented. Both hands are on the rock, so nothing can be held — and every climb clip in `mech_ladders@base` and the `narrow_ledge` set is authored unarmed, so a drawn weapon just stays welded to the hand through all of them.

The holster now happens in `attachClimbPhysics`, which is the **single funnel** every entry path reaches — manual grab, slide catch, failed native jump, midair regrab and reverse mantle. That covers all five without patching each transition separately, so a future entry path gets it for free.

It uses `SET_CURRENT_PED_WEAPON(ped, WEAPON_UNARMED, ...)`, the same idiom the prone module already uses for exactly this reason. That **stows** rather than destroys, so your weapon is still selected when you drop off — you shouldn't have to re-pick it.

It also logs `holstered on attach weapon=0x...` so the log proves which weapon was stowed, rather than this being assumed to have worked.

11/11 climbing verifiers pass, build EXIT=0, installed `7B4BC581…`.

Leaving open until you confirm in-game: hands empty on grab, and the weapon still equipped after dismount.
