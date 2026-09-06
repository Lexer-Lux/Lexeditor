# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356484028 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313

Created: 2026-08-30T19:39:43Z; updated: 2026-09-05T18:37:17Z

Exact metadata: [source record](sources/issue-5356484028-06a7a5310f0b2f37bae4d186c43e6f1dcb1f860adaeaf4776b568df40f70cd9d.json).

During a character's turn, L1 / Look Left opens the living reserve list. Confirm replaces that character and spends their turn. Cancel keeps the turn.

The first live test showed only a cursor. The missing names and panel are repaired. Shared Magic must remain off for this test; support for using both features still needs work.

Your check after installing the repaired build:
- [ ] Enable Party Switch with Shared Magic off. In a normal battle, press L1 during a character's turn. Confirm reserve names appear.
- [ ] Cancel once. Confirm the same character can still act.
- [ ] Open the list again and select a reserve. Confirm the character changes, their ATB starts empty, and the other two party members stay intact.
- [ ] Switch back later. Report any wrong HP, spells, model, or turn behaviour.


## issue 5356484028 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313

Created: 2026-08-30T19:39:43Z; updated: 2026-09-06T12:33:03Z

Exact metadata: [source record](sources/issue-5356484028-8f11f7aa11fd8f8850b74174af7a201986355ffa54e3f640c338b0ab1883a26d.json).

L1 / Look Left should open the living reserve list during a turn. Confirm swaps only the acting character and spends their turn; cancel keeps it.

**Status: Broken; repair not delivered.** The latest player test opened an empty panel and selecting a reserve soft-locked the game. Draft PR #356 repairs the replacement path, but its Windows driver still needs building and packaging. Do not repeat the old test yet. Shared Magic compatibility also remains unfinished.

## comment 5550344895 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313#issuecomment-5550344895

Created: 2026-08-30T20:30:57Z; updated: 2026-08-30T20:30:57Z

Exact metadata: [source record](sources/comment-5550344895-69325d44dc24b8f7049fc7b61a6496cf05ec466ad76bcc3ba5fc3bd65e25f1d3.json).

FF8 has a real battle reserve-replacement sequence, but it is hard-coded for encounter 0x01FF, auto-selects the lowest-EXP reserve, and schedules encounter callbacks. It does not provide the requested selector, cancel-to-same-turn path, or normal turn spend. The option remains fail closed rather than writing guessed party state.

## comment 5550344909 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313#issuecomment-5550344909

Created: 2026-08-31T05:49:29Z; updated: 2026-08-31T05:49:29Z

Exact metadata: [source record](sources/comment-5550344909-1497b46f880828e6a91d0531cd770b40012e579aaf8b7279fe9ee92a29c632f6.json).

Cause: Party Switch was still an explicit fail-closed placeholder. The existing Switch feature was Squall's GF-command swap, not FF10-style party replacement.

Party Switch now has its own reserve-character selector. Look Left is captured only by the battle command controller. The selector excludes current and unavailable characters, uses the game's dynamic character names, returns to the same turn on cancel, and sends confirmation through FF8's native full participant-replacement callback instead of writing the party array directly. The current mod has the tweak enabled and the generated patch passed the related shortcut, command-menu, Shoot, Draw, settings, and Party Switch checks.

This is not an in-game success claim. Please test one normal battle: open it with Look Left on an active character, cancel once, then confirm one reserve character. Confirm that only the acting character changes, the action consumes that turn, junctions and models remain correct, and Look Left still controls the field camera outside battle.

## comment 5550344925 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313#issuecomment-5550344925

Created: 2026-09-04T15:38:03Z; updated: 2026-09-04T15:38:03Z

Exact metadata: [source record](sources/comment-5550344925-986b7af6003bb3d84e0126b53df103f8a50979e2e0fdcbe2cf067dc930414244.json).

The latest executable audit found that the current party-switch hook at 0x004971F0 is specific to encounter 0x01FF, not a generic battle party-change path. Keeping it selectable would preserve a crash risk. The unsafe patch is now fail closed while the normal battle actor-replacement path is traced.

## comment 5550344931 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/313#issuecomment-5550344931

Created: 2026-09-05T06:51:13Z; updated: 2026-09-05T06:51:13Z

Exact metadata: [source record](sources/comment-5550344931-f3afa9436eb2ef29abdf5449f300d9bf277587fccbcc84c9c4f1b9b6d163e7c8.json).

Lexer confirms FFX-style Party Switch is disabled and absent. This matches the deliberate block documented above; it is unfinished, not a completed repair. Keep the full requested actor replacement and turn behavior outstanding. Deferred.
