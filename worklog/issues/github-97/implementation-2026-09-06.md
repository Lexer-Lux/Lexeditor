# #97 — Stock and WSE2 Play

The previous WSE2-only boundary is removed. Stock startup now selects the exact
installed module in its owned native launcher, not a guessed command-line flag
or name-only filesystem match. Selection is read back after CBN_SELCHANGE; only
real Play control 1029 is activated. Job assignment occurs before the suspended
process runs, so immediate child handoff is contained. Readiness excludes dialogs,
launcher controls and windows from other executables. Errors/timeouts clean up
only this job; failed cleanup retains ownership and Stop remains usable.

Tests: `python -m unittest discover -s tests -p 'test_warband*.py' -v`.
`test_warband_native.py` adds stock/WSE routing and real Windows GUI fixtures:
exact module selection, decoy exclusion, unrelated-window isolation, failure
cleanup, and immediate child-process handoff. These fixtures are not the game.

The native route has no new dependency or separately built runtime artifact.
Final cross-platform CI and master integration must be recorded before calling
this delivered. Actual Warband/Steam/WSE2 acceptance remains a prepared human test.

Test after updating master and restarting Lexeditor: select a built installed mod,
press Play, confirm that mod's menu and a loaded save, then Stop. Repeat for a
stock installation without WSE2 and for WSE2 when available. A broken disposable
module must restore Play with an error. Report module name, executable/version,
visible error and rgl_log.txt/WSE2 log. No live save or game asset is edited by Play.
