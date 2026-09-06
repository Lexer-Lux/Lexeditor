# #98 — Coverage and paging

Branch: `fix/warband-issue-batch`.

Warband Data Map now distinguishes structured editing, read-only views, source-only
access and unavailable source. Links explicitly open a browser/editor or source.
Missing source on installed modules no longer causes the whole plugin boot to fail.
The screen uses shared `pagedListDetail` with measured minimum row height rather
than the old fixed 100-row Data Map pager. Items and Troops also opt into fitted rows.

Local rendered fixture checks passed at 1200x800, 900x620 and 1600x1000. Data Map
reported respectively 15, 10 and 20 complete rows, body height equal to viewport,
and no master-list scroll overflow. Screenshots were inspected. These are fixture
UI checks, not proof of installed-game data coverage.

The issue also asks for a cross-plugin audit. That portion remains agent work and
is not silently claimed by this Warband-only batch. Other game agents may edit it.

Prepared owner test: open Data Map on this branch, filter Source only, inspect
module_skills.py, use Edit source, then close without changing it. Resize the window
and page forward/back; expect complete rows, reachable controls and no master
scrollbar. Installed modules without Python source should show Unavailable.
