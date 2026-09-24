# #316: Prepare controlled flying-evasion comparisons

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/316)

## Requirements and decisions

Flying enemies receive the configured evasion bonus against grounded melee. Ranged attacks and Float ignore only that flying bonus. Squall's gunblade hit-rate 255 intentionally passes through ordinary accuracy while the tweak is enabled rather than bypassing the rule.

## Current implementation and evidence

On 2026-09-06 the supported Steam-English executable hooks passed native execution/emulation checks across character/level coverage. The verifier also exercised the flying bonus, preserved non-flying behavior, gunblade-255 handling, and ranged/Float exceptions; the browser formula curve check passed separately. Gameplay-settings persistence/composition also passed through Save/activation.

The live issue is now `untested` with a high-signal Bite Bug comparison using a 100-point bonus, ranged and Float controls, and a grounded-enemy control. These automated checks do not claim stochastic battle acceptance.

## Next agent work

No implementation work is currently known. Preserve the controlled in-game comparisons in the live issue; investigate only if those observed hit/miss patterns contradict the verified model.
