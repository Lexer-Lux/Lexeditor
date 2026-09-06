# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356296222 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152

Created: 2026-08-06T02:37:03Z; updated: 2026-09-05T06:57:42Z

Exact metadata: [source record](sources/issue-5356296222-eac64a9aa022bd4e5cb835ed3cde2e5704f7cc07ba9fdbadc5e5a97224789dc6.json).


38.  LEXEDITOR SUPPORT FOR WEAPONS, WEAPON STATS, AND WEAPON MODS — I want to rework the weapon
     mods, maybe even make new ones, but I was looking at the improved accuracy
     from the improved iron sights and you said that changing it would only
     change the DISPLAYED change and not the actual change, so we need the
     editor to be able to show and change both actual and displayed changes
     together. But I think you also said weapon stats aren't even single
     quantifiable values, and the displayed values in the UI are just rough
     approximations of a bunch of other stats? See Lexer-Lux/Lexeditor#226.

## issue 5356296222 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152

Created: 2026-08-06T02:37:03Z; updated: 2026-09-06T13:07:23Z

Exact metadata: [source record](sources/issue-5356296222-32228652a5b725c0c279adcba535d33b0064b8ba325b30f9febbb6d86a80e0fb.json).

**Status: Latest Weapons layout and search repairs are ready for review.** Unresolved fields remain explicitly unidentified.

- [ ] Open Weapons → Cattleman Revolver. Expand several groups and scroll; confirm the details remain readable and do not trap scrolling in a hidden inner panel.
- [ ] Type RECOIL into field search one letter at a time, then Backspace. Confirm focus and the caret stay in the search field and matching groups open. Report the failed step or screenshot.

## comment 5550123806 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152#issuecomment-5550123806

Created: 2026-08-06T03:57:21Z; updated: 2026-08-06T03:57:21Z

Exact metadata: [source record](sources/comment-5550123806-88e62c5bb92a29306be546b8d88b88f7ab2f98677d313bc82381d0a4c4a21930.json).

Research result: actual and displayed stats should not be independent editable numbers. Shared ammo behavior lives in `CAmmoInfo`; per-weapon/per-ammo damage, penetration, accuracy, and falloff live in weapon `DamageInfos`; real component multipliers live in `CWeaponComponentInfo`; radial bars are UI summaries. LEXEDITOR already enforces the complete 11-file weapon stack and preserves unresolved fields. The correct UI is mechanical fields plus a read-only derived bar preview with source-layer provenance. The remaining research is Rockstar's exact normalization/clamping formula; until recovered, any preview must say “approximate.”

## comment 5550123822 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152#issuecomment-5550123822

Created: 2026-08-06T07:44:28Z; updated: 2026-08-06T07:44:28Z

Exact metadata: [source record](sources/comment-5550123822-0a678d136f98003aa8502c2a02b5c8f0a10cb820f26ef74ff3ee27a8011a2781.json).

Research complete.

The authoritative mechanical stack is:

- shared ammo behavior: `CAmmoInfo`;
- per-weapon/per-ammo damage, penetration, accuracy and falloff: weapon `DamageInfos`;
- attachment behavior: `CWeaponComponentInfo` multiplier fields;
- displayed radial bars: derived UI summaries, not independent weapon stats.

The files are also layered: base `weapons.ymt`, six Rockstar per-weapon patch YMTs, and four weapon-component layers (11 files total). Replacing/editing only the base file demonstrably restores Rockstar's pre-patch behavior, so LEXEDITOR is correct to require and preserve the full stack.

Conclusion: “actual” and “displayed” values must not be two independent editable controls. The truthful UI is editable mechanical source fields with source-layer provenance, plus a read-only derived preview. The extracted metadata and Story scripts do not expose Rockstar's exact radial normalization/clamping formula, so any preview must remain explicitly labeled approximate until runtime/UI reverse engineering recovers it. No further data-file research can turn the bars into authoritative values.

Human decision: whether an approximate derived preview is useful enough to build, or whether the editor should show only the real mechanical fields.

## comment 5550123835 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152#issuecomment-5550123835

Created: 2026-08-16T03:45:55Z; updated: 2026-08-16T03:45:55Z

Exact metadata: [source record](sources/comment-5550123835-6c3ebcbc93c4757b6e96b0700f3a084e05f9c6f332abfc7f5b0a0f170018827b.json).

Reworked the Weapons detail view. Settings now start in collapsed functional groups, field search opens matching groups, and the right pane grows with the page instead of using a hidden nested scrollbar. The left weapon list keeps its visible scrollbar. Meaningful field help is now available across the parsed record; unresolved schema fields stay in an Unidentified section with no filler tooltip. Please open Weapons, select a field-heavy gun such as the Cattleman Revolver, expand several groups, and confirm that the organization and page scrolling feel right.

## comment 5550123849 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/152#issuecomment-5550123849

Created: 2026-08-16T03:51:02Z; updated: 2026-08-16T03:51:17Z

Exact metadata: [source record](sources/comment-5550123849-ed70c18e41df3bcf8956a41d288e060a286c6d3043043db6e2695d4300310de6.json).

Fixed the returned Weapons field-search focus defect. The filter was inside the main pane, but the rerender helper looked only for replacement inputs in the toolbar. It now restores the replacement in the correct pane, keeps the caret and selection, and avoids moving the page. An automated keyboard test typed RECOIL one character at a time and then used Backspace; focus and the correct caret position survived every rerender without another click.
