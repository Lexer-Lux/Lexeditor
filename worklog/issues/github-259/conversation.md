# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356322453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/259

Created: 2026-08-10T18:29:30Z; updated: 2026-09-05T07:03:26Z

Exact metadata: [source record](sources/issue-5356322453-db2cbdd2249d3b93b489010e7c639e60a0f77181b5284dbd46485a4446866f81.json).

I've asked multiple times now for you to make it so that when walking or sneaking down a climbable ledge to make it so you reverse-mantle down it and go into climbing position.
How many more times do you want me to ask you?

## issue 5356322453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/259

Created: 2026-08-10T18:29:30Z; updated: 2026-09-06T12:56:49Z

Exact metadata: [source record](sources/issue-5356322453-f6e785531b65f6641c75d7aca944ca81330f3b5c4139ba582d24a258df89ce8a.json).

Walking or sneaking off a climbable ledge should reverse-mantle into a safe grip; sprinting should retain its separate behavior.

**Status: An earlier correction was installed, but later shared climbing/surface failures remain unresolved.** Verify the combined entry and contact handling before requesting another ledge test; do not assume the older candidate remains accepted.

## comment 5550153173 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/259#issuecomment-5550153173

Created: 2026-08-10T23:45:58Z; updated: 2026-08-10T23:45:58Z

Exact metadata: [source record](sources/comment-5550153173-b313164b2285d49d0b816da83de425e667ddc0d183d26f542dc85d6b100db2ea.json).

Installed the ledge-grab correction. Walking/sneaking off a ledge now uses below-root probes opposite actual movement, requires a multi-hit steep face, excludes running/sprinting, and plays Rockstar generic vertical-climb vault_down into the climbing anchor. Confirm walk and sneak entries visibly reverse-mantle into climbing rather than fall or use the old unrelated animation.

## comment 5550153208 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/259#issuecomment-5550153208

Created: 2026-08-14T06:10:34Z; updated: 2026-08-14T06:10:34Z

Exact metadata: [source record](sources/comment-5550153208-ffa1465ab6ee3190ecb83d06668bb0ba65ee948f1316c1e76ac8d012388588e6.json).

This correction is in the installed build, and I verified the climbing changes are physically present in the installed `.asi` rather than only in source — today I found two other "shipped" fixes that were dead code, so I stopped trusting that.

One thing worth knowing before you test: today's Lexer-Lux/Lexeditor#193 fix corrects the probe ray heights, which were being fired about a metre too high because the ped's origin is not at his feet. Ledge-grab entry depends on those same probes finding a surface, so this path may behave differently from when the correction was written.

Moving to `test me`. Walk off a ledge, then sneak off one, and confirm each reverse-mantles into climbing rather than falling or playing the old unrelated animation.

