# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356319645 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/250

Created: 2026-08-10T15:25:40Z; updated: 2026-09-05T07:02:56Z

Exact metadata: [source record](sources/issue-5356319645-fd966ac8735a9afdaecd8ac85bba6d4476502b19340b5945439b804721067d85.json).

 is there any way to make the PC's body "transparent" to the light from the lantern alone? because otherwise it will only light up one tiny area, with the rest of the light being blocked by his body....

## issue 5356319645 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/250

Created: 2026-08-10T15:25:40Z; updated: 2026-09-06T13:18:11Z

Exact metadata: [source record](sources/issue-5356319645-a18fbced2aa89022602509aa3ff2a599bb4da60ddc03a574ea84bee0001fc040.json).

**Status: Not supported by the checked light interfaces.** They provide no per-light exclusion for Arthur while retaining everyone else’s shadows. Global shadow changes would not satisfy this request. A different engine-level light mask would be needed; no fake workaround was installed.

## comment 5550150072 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/250#issuecomment-5550150072

Created: 2026-08-10T17:10:02Z; updated: 2026-08-10T17:10:02Z

Exact metadata: [source record](sources/comment-5550150072-05bad37e70d11e7555b085618499638c8e5f5986831d00866aed6020839b0fa9.json).

I checked the actual lantern-light and shadow interfaces rather than adding another fake workaround. Rockstar's DRAW_LIGHT_WITH_RANGE exposes only position, color, range, and intensity; it returns no light handle and accepts no excluded entity. The object/entity light controls likewise have no target-exclusion parameter, and the resolved shadow controls are global cascade or rope-only. So ScriptHook cannot make Arthur alone transparent to this lantern alone without also changing global/player rendering. I made no source mutation for Lexer-Lux/Lexeditor#250 and moved it from actionable to unfeasible. If a future engine hook exposes a per-light inclusion mask, this can be revisited.
