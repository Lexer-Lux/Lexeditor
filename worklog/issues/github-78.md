# #78: Use clear cached icons for Warband items

## Sources and requirements

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/78), [implementation session](github-78/implementation-2026-09-06.md) remain preserved. Replace the live thumbnail with a lit, consistently auto-fitted still render of inventoryMesh on neutral ground; retain the separate interactive preview. Serve cached PNGs through `/api/item-icon`, generate in the background, isolate module identities and invalidate only affected mesh/material/texture dependencies. Low priority was not a technical blocker; the subsequent all-Warband request resumed implementation.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. The deterministic software renderer and background cache worker are included. CI run 34040197660 passed cache reuse, module separation, dependency mutations, renderer framing, error/retry and actual temporary DDS pixel-regeneration tests. Browser fixtures verify the heading uses IMG rather than a second live canvas. These are synthetic assets, not installed-game appearance/performance acceptance.

## Remaining acceptance

After the normal master update, `tools/Warband-checks.cmd` runs the supplied disposable texture-mutation fixture and opens Warband. Do not edit installed textures to test invalidation. Check boots, helmet, sword and polearm; browse during initial generation, restart and revisit. Expect fully framed, static icons, responsive browsing and cache reuse. Report item IDs, missing/bad icons, stalls or repeat generation. The exact test is in `worklog/reference/warband-acceptance.md`; no rebuild is required. Keep open for actual-asset acceptance, not further planned implementation.
