# Worklog: 048 Todo Structure Feasibility Notes 2026 07 06

## TODO structure & feasibility notes (2026-07-06)

- TODO.txt now has a **PENDING CONFIRMATION** section: built items move there
  (not DONE) until Lexer confirms in-game. Per his instruction.
- **#6 skip startup movies** added. Method = LML blanks the boot movies
  (rockstar_logos / Title_GameIntro_1080p, mapped in movievariations.xml to
  .bik in movies_0.rpf). Can't author .bik from scratch (no open Bink encoder),
  so the clean route is editing boot data (startup.ymt in data_0.rpf) — needs
  a game-closed OpenIV session; bundle with the .ytd bake. Don't ship a blind
  boot-hang risk.
- **#2 skills feasibility:** mechanic is feasible as an .asi (own XP/save, 4
  levels, native toast popups; XP from COMPENDIUM_* natives — observed animals/
  entry counts + a plants-picked stat). NOT feasible: adding skills into the
  vanilla Player->Arthur attributes menu (engine-hardcoded enum PA_HEALTH… +
  scaleform). Proposed compromise: native toasts + a custom key-opened panel.
  **Awaiting Lexer's design decision before building.**

