# #20: Fit item previews and preserve Warband's game font

## Sources and requirements

[Verbatim request and discussion](github-20/conversation.md), [source records](github-20/sources/), and [implementation session](github-20/implementation-2026-09-06.md) remain preserved. Required: expose the first inventory mesh; resolve installed/module BRF and DDS dependencies without copying the full library; fit the heading icon; retain rotate/zoom/close/reopen; use the installed bitmap atlas and metrics for supported prominent labels, with legible native editable controls. Later corrections require preserved DDS alpha, centered shortcut badges, readable manuals and explicit missing-texture errors. Item-property editing is not part of this preview request.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. Cached heading PNGs, full-preview cleanup/dependency checks and installed font handling are available in the normal checkout. CI run 34040197660 passed Windows/Linux Python regressions, graph and rendered/WebGL fixtures. DDS alpha/metrics and missing dependencies have fixture coverage; no installed-game visual acceptance is claimed.

## Remaining acceptance

Update the normal checkout from master, restart, then run `tools/Warband-checks.cmd`. No driver or mod rebuild is needed. Follow Items in `docs/warband-acceptance.md`: boots/helmet/sword/polearm icons, preview rotate/zoom/close/reopen, rapid item/tab changes, tab lettering, badges and manuals. Report item/mesh IDs, screenshot and any visible error. Only installed-asset acceptance remains; failed acceptance returns this issue to actionable. Do not close solely from CI.
