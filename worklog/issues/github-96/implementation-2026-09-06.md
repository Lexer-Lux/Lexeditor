# #96 — Bottom-up troop trees

Branch: `fix/warband-issue-batch`.

Replaced flat upgrade edges with faction and connected-tree selectors, bottom-up
graphs and an in-view troop detail pane. Branches, independent roots/components,
merges, missing references and cycles are preserved. Selection is keyboard-operable.
Layout uses the shared resizable master/detail panels.

Node regressions cover factions, duplicate edges, branches, merge depth, cycle
termination, missing troops and empty input. Browser fixture checks cover root to
upgrade vertical order, selecting Knight details, independent trees/faction change,
and heading/body separation at 1200x800, 900x620 and 1600x1000. Screenshots inspected.
Actual Module System parser breadth and mod-specific graph appearance need acceptance.

Prepared owner test: open Troop Trees for your source mod, switch faction and every
available tree, select root/branch/end troops, resize and scroll a wide tree. Expect
roots at bottom, all branches retained and matching details at right without
switching tabs. Report the faction, troop IDs and screenshot for any incorrect link.
