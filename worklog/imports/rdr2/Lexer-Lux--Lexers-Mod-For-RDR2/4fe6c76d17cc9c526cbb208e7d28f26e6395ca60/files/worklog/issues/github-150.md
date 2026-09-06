# GitHub #150 — enforce `fuckups.txt` recurrence audits

## Trigger

The 2026-08-10 actionable batch repeated failure classes already documented in
`fuckups.txt`:

- #144 wrote move rate, minimum/maximum/desired blend and forced motion state on
  every owned frame, then produced severe visible animation stutter;
- #5 converted a screenshot into an unverified +90-degree local-axis guess,
  which moved the lantern into/behind the body;
- #55 and #62 were described as repaired from source/API checks without a
  rendered screen check; #55's returned screenshot contained literal
  `undefined` labels.

## Process repair

`AGENTS.md` now has an explicitly agent-authored safeguards section. It is not
placed under or attributed to Lexer's instructions. Before issue code, it
requires an issue-specific worklog audit covering primary evidence/reference,
the sanctioned engine path, execution/postcondition proof, every per-frame
mutation, and player-visible acceptance. It also explicitly rejects build,
hash, configuration, setter and syntax/API-only claims as behavior acceptance,
and requires rendered checks for visual/UI defects.

The nine actionables present when the failure was reported were assigned or
audited under that rule: #4, #5, #6, #8, #55, #62, #128, #144 and #147. #150
remains actionable until those audits are present and the combined batch passes
its issue-local checks; this process change does not claim that any game feature
is accepted in-game.
