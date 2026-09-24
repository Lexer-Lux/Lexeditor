# #309: Prepare an in-game True ATB Wait test

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/309)

## Requirements and decisions

When any living party member is command-ready, other party and enemy ATB gauges stop filling. Filling resumes only when nobody is ready. Animations and unrelated battle work must continue.

## Current implementation and evidence

The True ATB Wait runtime hook is integrated into FF8 gameplay-settings patch generation. On 2026-09-06 the supported Steam-English executable hook/guard contract passed privately, and the full Save/activation persistence/composition verifier passed with the tweak enabled and disabled. No game executable was published and automated checks do not establish observed battle behavior.

The live issue is now `untested` with a controlled battle setup using visibly different Speed values.

## Next agent work

No implementation work is currently known. Human acceptance must observe gauge freezing while a living character is command-ready, continued animations, persistence while another character is already ready, and resumption when nobody is ready, with the disabled tweak as control.
