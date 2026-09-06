# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356310129 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211

Created: 2026-08-06T06:47:02Z; updated: 2026-09-05T07:00:46Z

Exact metadata: [source record](sources/issue-5356310129-c3ab31def4b3a26f50ac62cda0b4174a9961e8ca7f060196d423b4c38e7340ba.json).

i star up the game. arthur is resting at the valentine campsite i placed. i hold f3 to remove it -- i wanna move it. it says "stand at an authored campsite to remove it". bruh that's what i'm doing. stranger still, if i just tap it it lets me place another campsite right on top of this one?

## issue 5356310129 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211

Created: 2026-08-06T06:47:02Z; updated: 2026-09-06T13:17:38Z

Exact metadata: [source record](sources/issue-5356310129-252d53dcf70a47293d4d43df3bf3be451f8010287bc206be3af7e7b9265004f5.json).

**Status: Closed after the installed removal repair.** Developer F3 removal and duplicate prevention use the same physical campsite footprint, including tent/rest positions. Holding F3 remains deliberate; normal player teardown protection is separate in #101.

## issue 5356310129 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211

Created: 2026-08-06T06:47:02Z; updated: 2026-09-06T13:55:06Z

Exact metadata: [source record](sources/issue-5356310129-b54b4aec4dc062cacd910b5108422f97a9e54873577cf8b69f64c0701a7f6dc1.json).

**Status: Closed after the installed removal repair.** Developer F3 removal and duplicate prevention use the same physical campsite footprint, including tent/rest positions. Holding F3 remains deliberate; normal player teardown protection is separate in #101.

## comment 5550139035 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211#issuecomment-5550139035

Created: 2026-08-06T06:48:02Z; updated: 2026-08-06T06:48:02Z

Exact metadata: [source record](sources/comment-5550139035-0b1908bf47500ad48cf88e139586c34014b673c0f8b116d9d8e7af01726a6285.json).

also I hit F2 and then some random card map marker from god knows how far away got moved there. can you put it back

## comment 5550139047 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211#issuecomment-5550139047

Created: 2026-08-06T07:11:11Z; updated: 2026-08-06T07:11:11Z

Exact metadata: [source record](sources/comment-5550139047-9188de7b3abcb7583ad411d9da7f205b8cc7263f3cdcde828eec05885363d881.json).

Fixed in source and queued for verified install. Removal only accepted Arthur within 8m of the saved fire origin, but the authored tent/rest positions can put him outside that radius; tapping also used a mismatched 10m duplicate check. Both now use the same 30m physical campsite footprint, while removal still requires the deliberate 800ms hold. The F2 trace also identified Flora of America Card 9 moved exactly onto that campsite and a later 94m Davey Callander move; I removed those last override rows so their prior/base positions return on restart. Keeping actionable until the install lands.

## comment 5550139060 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/211#issuecomment-5550139060

Created: 2026-08-06T07:19:06Z; updated: 2026-08-06T07:19:06Z

Exact metadata: [source record](sources/comment-5550139060-2dfdbb7f4705bd225582758e239a9c598e080071ebb118343bad4b4ebac77907.json).

Built and installed. F3 campsite matching now uses the campsite's full 30 m physical footprint for removal and duplicate prevention. I also fixed the separate per-frame player_camp relaunch storm and removed the two accidental collectible-location overrides. Please restart the game, then test hold F3 at the Valentine campsite, tap F3 there, physical cleanup, and the Flora/Davey markers.

Installed ASI SHA-256: `85C62841F5F6C8C5B2D069A0965D3AAFA703095B9B0B74876E7728BFE5ED5D32`
