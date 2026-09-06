# Worklog: 045 Hard Rules From Lexer

## Hard rules from Lexer

- `FEATURES.txt` is restored as of 2026-07-12. It contains only implemented,
  confirmed mod features. Only Lexer directs additions; Codex may remind him
  about eligible completed features but must not add them autonomously.

- **From scratch only.** Other mods are reference (schemas, values, approach).
  Never ship third-party files in a release. Current [DEBT]s (Kiddo-based data
  files, jaderloki-based challenges_sp.meta — repo has NO license) must be
  rebuilt from vanilla extracts before any distribution. Track debts in
  CREDITS.txt.
- **TODO.txt discipline**: numbered list; add items only when Lexer says to;
  move finished items to its DONE section.
- TODO categories must reflect demonstrated feasibility. `BLOCKED` is only for
  work with a concrete external dependency; unknown reverse engineering is not
  an external dependency. TODO #18 (bounty maximums) is DROPPED because no
  editable data, native, usable script global, hook, or reference implementation
  was found. Do not describe compiled-script behavior as editable without an
  identified mechanism.
- Script mods should be as small and config-free as their job allows. Config
  files only when live tuning is genuinely needed (CoreVignetteRamp keeps its
  ini because Lexer plans to customize the shader look/curves).
- Vignette taxonomy (took 3 rounds to converge — don't relitigate):
  the ALWAYS-ON ambient vignette must be REMOVED (pending timecycle
  extraction); vignettes belonging to gameplay FX (deadeye, low HP) STAY;
  empty-core FX must RAMP with outer-bar emptiness (CoreVignetteRamp remains in
  testing; do not call it done until Health/Stamina/Dead Eye all pass).

