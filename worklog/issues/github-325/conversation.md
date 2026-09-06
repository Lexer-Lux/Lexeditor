# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356486095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/325

Created: 2026-09-04T06:51:15Z; updated: 2026-09-05T07:40:08Z

Exact metadata: [source record](sources/issue-5356486095-7648cd4b7712d30bd125b15e26db1e733f65b3039c794c0988a091ffc6e15493.json).

Lexer's request:\n\n> enemies that cannot be turned into cards cannot be targeted with the card command menu ability. if there are no valid targets, the command menu option is greyed out.\n\nImplementation must share the existing command-eligibility dispatcher with Draw Once. It must not install a second patch over the same three hooks.

## issue 5356486095 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/325

Created: 2026-09-04T06:51:15Z; updated: 2026-09-06T12:59:57Z

Exact metadata: [source record](sources/issue-5356486095-cb63f317cfeda549a11b05caaf0d1bfef503afb24f293666f5a4ac6299a77cea.json).

Better Card should exclude enemies that cannot become cards and disable the command when none are valid, without conflicting with Draw Once.

**Status: The implementation passes code checks, but its player-test setup is incomplete.** Supply a specific mixed-validity encounter and an all-invalid encounter with the correct build/settings before asking you to find or invent those tests.

## comment 5550347141 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/325#issuecomment-5550347141

Created: 2026-09-04T16:32:42Z; updated: 2026-09-04T16:32:42Z

Exact metadata: [source record](sources/comment-5550347141-6a04506adab693f10ab48fedaa6f1fb7254991e2dd114deab2b16ac81a8cc85f.json).

Better Card is implemented as a default-off Tweak. It uses FF8's native Card predicate, removes only enemies whose common and rare Card results are both FF from the Card target mask, and disables the command when no valid target remains. It shares one dispatcher with Draw Once so the two Tweaks do not overwrite each other. Executable, composition, and mutation checks pass. Please test a mixed enemy group and a group with no cardable enemies in battle.
