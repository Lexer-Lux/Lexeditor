# Worklog: 077 Priority 0 Fixes 2026 08 04

## Priority-0 fixes — 2026-08-04

**Blank radial menus.** Regression from 41102d0 (#131, lantern removal). The
edit deleted the two `<Item key="WEAPON_MELEE_*_LANTERN">` opening tags and
their `<Slots>` bodies out of `MyOverhaul/quickselectitems.ymt` but left both
sets of `</Slots></Item>` closers behind, so the file was not well-formed XML
and the game silently failed to parse it. Every radial segment it feeds came up
empty; the hat survived because it does not come from this file.
Removed the four orphan lines. The file now parses, and diffing it against
`quickselectitems.ymt.pre-lantern` shows exactly the intended 16-line lantern
deletion and nothing else. `lml/MyOverhaul` shares storage with the repo copy —
identical md5 after the edit — so the fix is already live for the next launch.
Lesson: validate a .ymt/.meta with an XML parse after any hand edit. A malformed
data file does not error, it just goes blank.

**TODO.txt folding.** Root cause found, not patched over. Notepad++ folds that
file by tag, and `#185` contained a `<Dropped>` written mid-sentence. That
unmatched opener made the lexer pair `</Actionable>` with it, so folding
`<Actionable>` swallowed everything to EOF. Reworded to "the Dropped section".
`tools/check_todo.py` now rejects any section tag that is not at column 0, so
this cannot return; AGENTS.md carries the rule.

**Agent instructions out of TODO.txt.** Header trimmed to a legend for Lexer
(sections, classes, suffixes) and the "Lexer's inbox / the agent turns it into"
parenthetical deleted from `<Processing>`. Everything removed was already
stated in AGENTS.md, so nothing was lost.

