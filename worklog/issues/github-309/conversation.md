# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356483398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/309

Created: 2026-08-30T20:50:32Z; updated: 2026-09-05T07:39:28Z

Exact metadata: [source record](sources/issue-5356483398-437cde9ebba147d44548e6a30ac0e5c7ee2b84d816094c7bb809452a72cb8b8d.json).

Add an independent, default-off gameplay setting.\n\nWhen any living party member can choose an action because their ATB bar is full, stop ATB filling for every other party member and every enemy. Resume ATB filling after no party member is actionable.\n\nUse the game's existing Wait-mode pause path. Do not zero timers, simulate a menu input, or freeze animation and unrelated battle work.\n\nPlayer check:\n- Enable the setting.\n- Enter a battle with different Speed values.\n- Let one party member become ready without choosing a command.\n- Confirm every other party and enemy ATB bar stops immediately.\n- Spend or cancel that ready state.\n- Confirm ATB filling resumes only when no party member is ready.

## issue 5356483398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/309

Created: 2026-08-30T20:50:32Z; updated: 2026-09-06T12:59:29Z

Exact metadata: [source record](sources/issue-5356483398-f829148f46fcc76c8e8af846fff4b824f8567c288691c3e3f241dbf050de7e58.json).

When a living party member is ready to choose an action, pause other party/enemy ATB filling. Resume only when nobody is ready, without freezing animations or unrelated battle work.

**Status: A current delivered implementation is not established.** Verify the runtime and prepare a battle with clearly different Speed values before requesting acceptance.

## issue 5356483398 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/309

Created: 2026-08-30T20:50:32Z; updated: 2026-09-06T12:59:29Z

Exact metadata: [source record](sources/issue-5356483398-f91f9766179fb19ef38f9376c44e25952704a43e5588cea40b78261abf93aa5e.json).

When a living party member is ready to choose an action, pause other party/enemy ATB filling. Resume only when nobody is ready, without freezing animations or unrelated battle work.

**Status: A current delivered implementation is not established.** Verify the runtime and prepare a battle with clearly different Speed values before requesting acceptance.
