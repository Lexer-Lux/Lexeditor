# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356325916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271

Created: 2026-08-11T04:33:12Z; updated: 2026-09-05T07:04:02Z

Exact metadata: [source record](sources/issue-5356325916-fdba7591b6725207933452d01580f58619238e56d879af2c5e2eb4fcba61f215.json).

(No body was present in this captured version.)

## issue 5356325916 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271

Created: 2026-08-11T04:33:12Z; updated: 2026-09-06T13:18:31Z

Exact metadata: [source record](sources/issue-5356325916-08feb81bb871b8244ab02ed1f62d842139e6e132c80fd89fda7d89383c98bc83.json).

**Status: Closed historical report.** Full stamina cost is required before admitting a roll. Its last user report still described a dive fallback, which is separately recorded in #283; current combined dodge behavior remains in #106.

## comment 5550158831 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271#issuecomment-5550158831

Created: 2026-08-11T09:32:43Z; updated: 2026-08-11T09:32:43Z

Exact metadata: [source record](sources/comment-5550158831-5f524a1edd0c865d403431fd617cc4fdcdea4b72015b229b4f2ddcb7ff50977c.json).

The roll gate now checks the full configured stamina cost before input reaches Rockstar, suppresses only INPUT_DIVE when unaffordable, and checks again when a queued roll is issued. Jump and climb inputs are untouched. Drain the bar below one full roll cost and try the roll, then try again at exactly the cost.

## comment 5550158856 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271#issuecomment-5550158856

Created: 2026-08-12T12:03:23Z; updated: 2026-08-12T12:03:23Z

Exact metadata: [source record](sources/comment-5550158856-8ab4c6ff38893ffdc7ec8c762b7d59f9ab9c66f4eeaed21f6aa0b44f0b454f57.json).

lol that didn't mean "go back to diving if you try to roll without stamina". you should do neither

## comment 5550158874 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271#issuecomment-5550158874

Created: 2026-08-12T13:07:35Z; updated: 2026-08-12T13:07:35Z

Exact metadata: [source record](sources/comment-5550158874-f0440a10445392553dd978f74068815b828d950eb59b2115f0ac7ae55d005b5b.json).

Roll admission now requires the full configured cost in both live Stamina readings and suppresses Rockstar's Dive input while either meter cannot pay. Test below cost: neither roll nor dive may start. At or above cost in both readings, one roll must start and charge once.

## comment 5550158886 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/271#issuecomment-5550158886

Created: 2026-08-13T01:43:01Z; updated: 2026-08-13T01:43:01Z

Exact metadata: [source record](sources/comment-5550158886-b69eb10f1638528eb2966596ede511994b1e47bccc0a66e62ff841e67bb56235.json).

??? you ddin't fix anything he still just dives when there's not enough stamina.
