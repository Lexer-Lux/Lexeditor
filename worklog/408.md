# #408: Finish New Formulae tweak and enumerate every changed formula

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/408)

## 2026-09-22 misc-fixes: Mug contract implemented

The blocker asked for the Difficulty-to-stored-rate contract to be made
explicit before touching the native Mug comparison. Done in
`plugins/ff8/formulae_rework.py`: `mug_difficulty_from_rate` maps the stored
Mug rate byte (0-100, higher is easier) to Difficulty (100 - rate), and
`mug_stored_success_chance` applies the requested formula to a stored byte
while keeping vanilla immunity for rate 0. Two committed tests cover the
mapping, the immunity edge, and invalid input; the full file passes (10
tests). The mug row stays `incomplete` with `runtime` unset, as the locked
contract test requires. Design decision for Lexer: rate 0 stays immune
rather than following the raw formula; say the word if the formula should
rule there instead. Remaining native work: the actual Mug comparison patch,
plus melee, magic-damage, and status-infliction patches (#31). Issue stays
`actionable`.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
