# #98 — Coverage and paging

Completed the cross-plugin audit in codex/data-map-coverage.md. All seven UI
implementations (including both FF7 editions) use the shared Data Map component,
which now composes the fitted Table + Detail view instead of fixed 100-row slicing.
Warband no longer duplicates its map shell. Claims distinguish structured partial
support, read-only interfaces, source-only access and unavailable files. FF7 links
individual KERNEL categories; FF9 links the exact CSV dataset; FF8 links the actual
subview. RDR generated metadata is reconciled against actual supported sources.
RDR2 preservation-only component layers and inactive projectile runtime controls
are no longer called editable.

Local coverage tests passed. Actual plugin HTML/CSS/map adapters were rendered
with in-memory fixtures at 900x620, 1200x800 and 1600x1000; notes scroll only in the
detail pane, the master has complete rows, and there is one shared pager. Added
pagination stability and source/read-only link checks. No installed game files
are touched by these tests. Final CI and merge evidence are recorded separately.

Prepared test after updating master: open Warband Data Map, select module_skills.py,
confirm Source only and explicitly labelled source editing, then close without
changes. Select Items/Troops rows and follow their read-only view links. Resize,
filter, sort and page; no master scrollbar or partial row should appear. Check
another plugin's Data Map: an unavailable source cannot claim editable support.
