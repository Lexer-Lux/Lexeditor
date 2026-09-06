# #78 — Cached inventory PNGs

Branch: `fix/warband-issue-batch`.

Added `/api/item-icon`, a deterministic software z-buffer renderer and a deduplicated
background cache/warm-up worker. Fixed fitted three-quarter view, lighting and neutral
ground replace the live icon canvas. PNG cache identity includes module, mesh BRF,
material BRF, DDS, reader and icon renderer revision. Foreground requests promote
queued warm-up work; generation errors are visible and retriable. Dependency changes
between queueing/rendering cannot write new pixels under an old key.

Tests cover repeatable PNG rendering, fitting, cache reuse, dependency invalidation,
wrong-key prevention and failure propagation. Browser fixtures confirm an IMG in
the icon slot with no thumbnail canvas. Real installed asset batch speed and visual
acceptance remain unmeasured. Local browser has no WebGL; full-view rendering is not
claimed from those fixture screenshots.

Prepared owner test: select a sword, armour, boots and horse; expect lit static icons
and a separate rotatable preview. Restart and revisit them; icons should reuse cache.
In a disposable module copy replace a referenced DDS or BRF, then reopen that item;
expect the icon to regenerate. Switch between two mods with the same mesh name and
confirm each uses its own assets. Report item IDs and screenshots for bad framing.
