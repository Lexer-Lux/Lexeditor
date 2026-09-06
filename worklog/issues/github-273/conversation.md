# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356326488 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/273

Created: 2026-08-11T06:11:44Z; updated: 2026-09-05T07:04:09Z

Exact metadata: [source record](sources/issue-5356326488-f4f83c12f9d48f4804cc0ed3118cb59fb25fa931e415e95eee163f89373bf78c.json).

It's...mostly gone. But sometimes returns. No consistent trigger. It seems to vary based on location and even facing direction. Maybe connected to equipping the lantern and being near the Valentine stables, too? Those seem to trigger it a lot.
Anyways. There are mods out there that remove the vignette. And as far as I'm aware, they don't have this issue. So you should DL them, decompile, and use them as reference to build a better vignette remover without these problems.

## issue 5356326488 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/273

Created: 2026-08-11T06:11:44Z; updated: 2026-09-06T13:18:32Z

Exact metadata: [source record](sources/issue-5356326488-deb9b96a75e15bdeccffd6478e71f883f5e43a8c5dbf066ae0dafd2f4bae3329.json).

**Status: Closed after the broader data correction.** The earlier remover covered weather presets but missed local modifier libraries. The correction also removes vignette from those libraries while preserving unrelated post-processing values.

## comment 5550159525 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/273#issuecomment-5550159525

Created: 2026-08-11T08:55:31Z; updated: 2026-08-11T08:55:31Z

Exact metadata: [source record](sources/comment-5550159525-6f5730a63684288c68617a6ec1b3b6d2bb1f75d040a8ec7fc182343cd4566194.json).

The missing path was the local timecycle modifier libraries. The old remover changed weather presets but skipped those libraries, so a location, viewing angle, or light could restore the vignette. I now zero the vignette field in every timecycle file that defines it, including the two modifier libraries, without changing the other post-processing values. On the next launch, rotate at the Valentine stables and toggle the lantern; the edge darkening should remain absent.
