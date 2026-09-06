# #97: Make Play actually launch Warband

## Sources and requirements

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/97), [native/WSE2 implementation](github-97/implementation-2026-09-06.md) and [exit-tracking correction](github-97/exit-tracking-2026-09-06.md) preserve scope and evidence. Play must start the selected built installed module in a usable game window, not merely obtain a process handle. Failed launch restores Play with an error; Stop owns/tracks/closes the actual launched session, including child handoff. Both stock Warband and WSE2 are in scope.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7; final repair commit 4bfc39638731eab734674b41387d954646cf0186. Stock uses its owned real launcher controls with exact selection/readback and real Play control 1029; WSE2 uses its documented selected-module command. Job assignment precedes execution. Retained process handles now prevent early Stop completion while Windows still holds files/directories.

CI run 34040197660 passed Windows and Linux regressions, real Win32 launcher/child-handoff fixtures, the twelve-cycle directory-release stress test and one-click diagnostic. The two new deterministic exit regressions fail against the old implementation. The full suite is 42 Warband + 7 coverage tests; platform-specific cases skip outside Windows. RDR1 and FF8 companion workflows also passed. This proves fixtures, not a real Warband/Steam/WSE2 session.

## Remaining acceptance

Use the normal updated master checkout; `tools/Warband-checks.cmd` runs disposable diagnostics and opens Warband. No build is needed. Select a built module installed under this game's Modules directory, press Play, confirm the selected mod's menu and load a save, then Stop. Test stock on an installation without WSE2 and WSE2 where available. Errors must restore Play with an explanation and Stop must affect only the owned session. Report executable/version, module, visible error and relevant rgl_log/WSE2 log. Details are in `worklog/reference/warband-acceptance.md`. Actual game acceptance is unverified; implementation and delivery are no longer pending.
