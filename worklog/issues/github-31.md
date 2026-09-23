# #31: Finish the Formulae Rework

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/31)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-22 misc-fixes status
Healing and accuracy runtimes stand (tests green). Melee, magic-damage, and status-infliction patches are still missing: each needs hand-written x86 against its routine, which cannot be validated without the game, so no blind machine code was written. Mug prerequisite done on this branch (explicit Difficulty contract plus tests, see github-408.md); the Mug comparison patch itself remains. Formulae page scroll report still needs a rendered check. Issue stays actionable.

## 2026-09-23 misc-fixes status
Scroll report resolved and fixed: the Formulae tab mounted a bare detailPanel while the FF8 plugin clips #main (`--lex-main-overflow:hidden`), so stacked cards below the fold were unreachable (reproduced headless: last card bottom 819px at 800px viewport, no scroll path). Fix wraps the panel in the shared `.lex-tweaks-scroll` container in `renderFormulae` (plugins/ff8/boot.js). Verified by new `tests/ff8_formulae_scroll_browser_check.py` (stubbed data, no game, no writes; wired into native-regressions.yml): scroller scrolls and last card lands inside the window. Melee, magic-damage, status-infliction and Mug-comparison runtime patches still need the game; issue stays actionable.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.

## 2026-09-23 formulae-subtab status

Per Lexer's latest comment, Formulae is now a subtab under Tweaks that
unlocks only while the Formulae Rework tweak is enabled (plugins/ff8/boot.js):
the owning toggle moved into the Tweaks Gameplay list (still unavailable
until every contract row has a runtime patch), `navigate('formulae')` lands
on Tweaks, and a locked subtab falls back to the Gameplay list. Page content
and the scroll-container fix are unchanged. Verified: rewritten static
contract (`tools/verify_ff8_formulae_issue_31.py`), extended stubbed scroll
check (content + lock fallback), rendered Tweaks check against the installed
game (`tools/verify_ff8_formulae_visual_31.py`), tabs font check. Still needs
the game: melee, magic-damage, status-infliction and Mug-comparison runtime
patches (no blind x86 written). The FF8 review/mod Google Doc is a Drive-only
`.gdoc` link and could not be read from disk, so the "did you miss any
formulae" audit against Lexer's doc is still open.

## 2026-09-23 per-game-ff8: verify-only, still needs the game

Re-verified on branch per-game-ff8: Formulae subtab gating and the scroll
fix stand as merged, and `tests/test_ff8_formulae_rework.py` is green in
the full ff8 unit run. No new code: melee, magic-damage, status-infliction
and Mug-comparison runtime patches still need hand-written x86 against the
game and were deliberately not written blind; the Google-Doc formulae audit
is still open (Drive-only .gdoc, unreadable from disk).

Needs Lexer/game: in-game verification of the four runtime patches,
Formulae scroll confirmation at an 800px viewport, and the review/mod doc
formulae section (paste the text or grant access).

## 2026-09-23 impl/ff8-actionables: verified, no new code

Re-verified on this branch: Formulae subtab gating, scroll fix, and
`tests/test_ff8_formulae_rework.py` stand as merged (green in the ff8
unit run). No new agent-side slice exists: melee, magic-damage,
status-infliction and Mug-comparison runtime patches need hand-written
x86 against the game and were not written blind; the review/mod-doc
formulae audit is still open (Drive-only .gdoc, unreadable from disk).
Stays actionable; needs the game-session checklist already on the issue.
