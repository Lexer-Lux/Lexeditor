# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356291059 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/130

Created: 2026-08-06T02:08:01Z; updated: 2026-09-05T06:56:28Z

Exact metadata: [source record](sources/issue-5356291059-8bf81133b51330048d71493d7567995db223c29452c1f96596e42e505917cc5d.json).

Req. Lexer-Lux/Lexeditor#126 
     Health, Stamina and Dead Eye tonics get upgradeable active capacities.
     Overflow goes to persistent storage; camp visits and death refill from
     storage highest-tier first, and tell me when a full refill isn't possible.

## issue 5356291059 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/130

Created: 2026-08-06T02:08:01Z; updated: 2026-09-06T12:46:55Z

Exact metadata: [source record](sources/issue-5356291059-781aa0e80022181619bcd4b5a279adfc0de5032dd20d01b38656c61e8a610add.json).

Give Health, Stamina and Dead Eye tonics upgradeable carried capacities. Store excess persistently and refill from highest-tier stock at camp or after death, warning when stock is insufficient.

**Status: Not ready.** The premature separate implementation was removed. Complete shared overflow storage in #126 before building this on it; there is nothing to retest yet.

## comment 5550117695 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/130#issuecomment-5550117695

Created: 2026-08-06T07:11:08Z; updated: 2026-08-06T07:11:08Z

Exact metadata: [source record](sources/comment-5550117695-b42c00bd3cc557f3eb79eaa57ed5c94c20230d73e9212fb61bb5169f724187cb.json).

Implementation update: integrated shared active capacities for Health Cure, Bitters, and Snake Oil families, with weak/standard/potent/special tiers. Overflow is moved into verified persistent storage; entering camp or completing respawn refills highest tier first and reports exact shortfalls. Base caps are INI-driven at 3, and shipped Master Hunter/Herbalist/Weapons Expert rank progression adds to the corresponding family. All 12 target catalog records accept overflow capture, static catalog checks pass, and the combined release builds. Keeping actionable until verified install.

## comment 5550117713 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/130#issuecomment-5550117713

Created: 2026-08-11T07:02:06Z; updated: 2026-08-11T07:02:06Z

Exact metadata: [source record](sources/comment-5550117713-6189c74d652301ff51c85894a5e25d284ec2ff463d253b10e6a8d94469da9df8.json).

You were right: this feature should not have existed as a separate runtime module. Lexer-Lux/Lexeditor#130 is explicitly blocked by Lexer-Lux/Lexeditor#126, because camp-rest tonic refill must use the shared DS3-style overflow storage and campsite inventory rather than inventing its own reserve and camp detector. I removed the premature module from the compiled runtime and removed its settings. Lexer-Lux/Lexeditor#130 remains open and blocked by Lexer-Lux/Lexeditor#126; there is nothing to test until that shared storage design is implemented.
