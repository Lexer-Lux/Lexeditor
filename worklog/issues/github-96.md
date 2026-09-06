# #96: Show bottom-up troop trees by faction

## Sources and requirements

[Verbatim request and discussion](github-96/conversation.md), [source records](github-96/sources/), and [implementation session](github-96/implementation-2026-09-06.md) remain preserved. Replace the flat upgrade list with selectable faction/tree groupings, bottom-up nodes and visible upgrade connections. Preserve distinct branches and multiple trees per faction; selecting any node shows that troop's matching right-side details. The later all-Warband instruction resumed the previously deferred work.

## Delivered implementation and evidence

PR #361 merged to master as bc6f97ef456b0a20b08358612c26eb400c97d2e7. The normal editor now includes the faction/tree selectors, connected graphs and shared detail pane. CI run 34040197660 passed Node regressions for branches, merges, cycles, missing nodes and empty input plus actual HTML fixture checks at 900x620, 1200x800 and 1600x1000. The narrow tree screenshot was inspected; this is not evidence about a particular installed mod's troop data.

## Remaining acceptance

Update the normal master checkout, restart or run `tools/Warband-checks.cmd`, and select the Warband source mod. In Troop Trees switch faction and tree; click root, both branches and an end troop. Roots must be below upgrades and right-side details must match. Resize/scroll a wide tree. Report faction/troop IDs and screenshot for missing or incorrect links. `docs/warband-acceptance.md` contains the prepared test. No driver/mod rebuild or new design answer is required; only mod-specific acceptance remains.
