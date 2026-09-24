# #326: Validate the raised 60,000 damage cap

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/326)

## Requirements and decisions

This tweak raises the ordinary 9,999 clamp to FF8's existing 60,000 path. It is a higher cap, not unlimited damage, and acceptance needs both a >9,999 case and a >60,000 clamp case.

## Current implementation and evidence

The supported Steam-English executable guard/static contract passed privately on 2026-09-06. Enabled and disabled states persist and compose correctly in the activated gameplay-settings patch. Formula/weapon controls provide a deterministic way to prepare ordinary physical damage above both thresholds; automated checks do not establish displayed in-battle damage.

The live issue is now `untested` with an ordinary gunblade damage setup, a 60,000 clamp check, and the disabled-tweak 9,999 control.

## Next agent work

No implementation work is currently known. Close only after the in-game ordinary-damage checks confirm >9,999 output, the 60,000 ceiling, and restoration of the vanilla clamp when disabled.
