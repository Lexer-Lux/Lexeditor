# #20 — Real meshes, complete dependencies and native bitmap labels

Branch: `fix/warband-issue-batch`.

Existing BRF/DDS/font implementation retained. Fixed installed-module resource root,
strict mesh/material/diffuse checks, cache invalidation for separate material BRFs,
source path validation and per-module cache identity. Prominent item/tree headings
now use the installed bitmap text helper; editable content stays native HTML.
Only enable the full preview control after dependency decoding and renderer startup.
Close disposes the renderer/listeners; opening rebuilds it; navigation disposes it.
Old source/visual checks now expect a cached PNG and one full-view canvas.

Fixture tests check exact DDS alpha preservation and font metrics, missing dependencies,
cache separation and error states. Local rendered tests confirm disabled/error UI
for missing texture and unavailable WebGL; they cannot verify a real in-game asset.

Prepared owner test: select boots, armour, a weapon and horse; rotate/zoom/reset,
close/reopen, and switch items quickly. Expect real textures, no stale model, and
readable installed font labels. On a disposable module with a missing diffuse DDS,
expect an unavailable message and disabled preview control, not a gray placeholder.
Report item/mesh IDs and screenshot for any mismatch.
