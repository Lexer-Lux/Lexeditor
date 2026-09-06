# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286931791 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46

Created: 2026-08-29T13:54:29Z; updated: 2026-09-05T06:27:54Z

Exact metadata: [source record](sources/issue-5286931791-ce20fcdcff9ba0dbf3daa5aa2887c5746b458f570eaf082cfdcf8c94cc231377.json).

Replace the old view-type architecture with reusable panel composition.

Decisions:
- A panel type owns its internal behavior and appearance.
- A tab layout only arranges panel instances, their sizes, and their relationships.
- The RDR2 record detail panel is the default Detail panel template for every plugin. Games can theme and extend it without rebuilding its basic structure.
- The old list-detail view is a two-panel composition: Table + Detail.
- The RDR2 Shops screen is a three-panel composition, not a separate three-panel view type.
- Existing pagination, fitted rows, sorting, N-barrels, split handles, selection, and history remain capabilities of panels or the layout composer.
- Plugins declare a layout and supply data/render adapters. They do not duplicate panel shells.

Initial panel library:
1. Table — dense selectable/sortable/filterable records; optional paging and N-barrels.
2. Detail — RDR2-style record heading, identity, grouped fields, provenance, actions, and help.
3. Selector — compact peer navigation using text, icons, portraits, or thumbnails.
4. Tree — hierarchical records such as nested loot, recipes, and dependencies.
5. Preview — images, icons, 3D models, graphs, loading, unavailable, and error states.
6. Activity — ordered comments, logs, history, reports, and optional bottom composer.

Do not create a panel type for a one-off visual variation. A new type requires distinct repeated behavior that cannot be expressed as a configuration of an existing type.

Migration must preserve current rendered behavior until each tab is converted and visually verified.

## issue 5286931791 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46

Created: 2026-08-29T13:54:29Z; updated: 2026-09-06T13:06:48Z

Exact metadata: [source record](sources/issue-5286931791-85750c82e04b8f52d8d3ae471394384e266626fc5ed39975c11452f8808b810a.json).

Use consistent resizable panels rather than different layouts rebuilt by each plugin.

**Status: Latest divider and text-fitting repairs are ready for review.**

- [ ] Restart Lexeditor. In RDR2, inspect Effects and Behavior IDs at 1600×900 and 1280×720. Confirm complete names/IDs, usable details and no clipped bottom row.
- [ ] In Blank’s panel examples, drag a dotted divider and resize it with the keyboard. Confirm selection and panel contents remain intact.
- [ ] Report the view, window size and screenshot of any layout mismatch.

## comment 5463009793 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5463009793

Created: 2026-08-29T14:37:40Z; updated: 2026-08-29T14:37:40Z

Exact metadata: [source record](sources/comment-5463009793-8a2cd1a51de8df3125229ca171dcf548bf94bb5531c7e4fac2206716b9e7d41d.json).

Add a standard optional top-left icon/preview slot to the shared Detail panel heading. It must accept flat icons or live preview content. Warband Items will be the first migration: its slot uses the real inventory-mesh render, while the existing full model preview remains available. Other plugins must migrate through the same helper rather than copy its markup.

## comment 5463026763 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5463026763

Created: 2026-08-29T14:41:21Z; updated: 2026-08-29T14:41:21Z

Exact metadata: [source record](sources/comment-5463026763-8bc88ef745e3c4faf5517dc128920a79493f9a1ad0c1286175ad8a4006528b96.json).

The shared Detail helper now owns an optional top-left icon or live-preview slot, identity, metadata, and actions. Warband Items is the first completed migration and uses its real inventory-mesh render in that slot. The issue remains actionable because the other plugin detail panels still need controlled migrations and separate visual checks.

## comment 5464405756 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5464405756

Created: 2026-08-29T19:29:56Z; updated: 2026-08-29T19:29:56Z

Exact metadata: [source record](sources/comment-5464405756-f1d3ebf3d5a30d053dae6feab714789f79b69a2b9e3ceb628353d38774a659da.json).

Panel resizing now belongs to the shared layout composer. It inserts a handle between every pair of sibling panels, so two panels get one handle and three panels get two. FF8 GFs, RDR2 Shops, and the GitHub workspace now use that composer; the old list-detail names only delegate to it for compatibility. Rendered pointer and keyboard tests passed, saved sizes stayed page-specific, and narrow layouts stacked without plugin-owned splitter code. The issue stays actionable for the remaining controlled panel migrations.

## comment 5464680159 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5464680159

Created: 2026-08-29T20:21:04Z; updated: 2026-08-29T20:21:04Z

Exact metadata: [source record](sources/comment-5464680159-ba0d990cfd4430b94be8765cac6d2e6c5fc2129115597bc4c2949a4fa430ac9d.json).

The shared Table panel must always use fitted complete rows, no internal scrollbar, paged navigation, and mouse-wheel page changes. This behavior must follow the panel archetype across every plugin, not only FF8 callers.

## comment 5464858450 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5464858450

Created: 2026-08-29T21:01:00Z; updated: 2026-08-29T21:01:00Z

Exact metadata: [source record](sources/comment-5464858450-f793ac55911b844a1d7df98a06e0a336ffcca2f1c3bc7a87bcfbc6992b63eb8d.json).

The shared Table behavior now fits complete rows, hides its scrollbar, uses the fixed bottom pager, hides that pager for one page, and changes one page per wheel gesture across the migrated FF8, RDR1, RDR2, and Warband record panels. I also removed RDR1's outer document scrollbar. The broader Detail-panel migration remains open.

## comment 5466538745 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5466538745

Created: 2026-08-30T03:45:38Z; updated: 2026-08-30T03:45:38Z

Exact metadata: [source record](sources/comment-5466538745-062b1d60435c9bc136d999dcc861fffeb2c913e98ccf248862f9ddd7b9e81689.json).

Added the next shared Detail-panel layer: Detail groups own section dividers, Detail rows own one fixed label/value split, and provenance keeps a reserved rail so controls do not move when references appear. FF8 Magic now uses compact General, Junctioning, and GF Compatibility groups; FF8 GF General no longer carries an instance-only fake header gap. The broader migration remains actionable.

## comment 5466776131 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5466776131

Created: 2026-08-30T04:49:39Z; updated: 2026-08-30T04:49:39Z

Exact metadata: [source record](sources/comment-5466776131-8108fb95c1e90b1ee6a56f0dd30341414da3b3e09321a13254b546ab454d9ce5.json).

Removed the conflicting late FF8 panel overrides that caused blue right panes, transparent captions with border lines through the text, and case-by-case Detail geometry. FF8 Detail rows now share one fixed label/value division, Weapons uses the shared row structure, and fitted tables measure their actual rendered rows so the border ends with the content instead of clipping it. Fresh rendered checks cover Items, Magic, GFs, Shops, and Weapons; the broader cross-plugin Detail migration remains actionable.

## comment 5466857353 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5466857353

Created: 2026-08-30T05:11:35Z; updated: 2026-08-30T05:11:35Z

Exact metadata: [source record](sources/comment-5466857353-a08c109d6fc7a96c910ce9279c1e86cce0427a8dec9bc68bd2e8b1a0018c757f.json).

Shared Table sizing now has one global Rows per page setting (5–40, default 15). A full page stretches exactly that many rows across the available height and matches the adjacent Detail panel; a short final page ends after its last record. FF8, RDR1, and Warband rendered checks passed without internal scrollbars. The broader Detail-panel migration remains actionable.

## comment 5470401183 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5470401183

Created: 2026-08-30T18:11:13Z; updated: 2026-08-30T18:11:13Z

Exact metadata: [source record](sources/comment-5470401183-bf2e3f8991ebdfb0c8f25b43b4f44b3f3209402c17864cbef1a5e5f73f0fb2ef.json).

Developer Mode now has a per-page Rows override for each Table page. A one-page result removes the center page controls and expands Search. High-density cells use one-line ellipsis, Thing Finders use stable cell tracks, and the two global number settings no longer use Chromium's white styling or text shadow.

## comment 5470548704 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5470548704

Created: 2026-08-30T18:41:00Z; updated: 2026-08-30T18:41:00Z

Exact metadata: [source record](sources/comment-5470548704-c1a8b2541e63369e68d38da9f05304709be078ab5cf832771eef20586b59dc8b.json).

The compact FF8 Detail controls are repaired through shared layout rules. Magic Element, J-Element, and J-Status toggles no longer have nested dark tiles; Magic GF Compatibility fits one aligned desktop row; compact labels align with their inputs; and Items Use Flags keeps each checkbox, label, and help marker together without overlap. Global Settings now forms multiple columns and has no scrollbar when the cards fit. The broader Detail-panel migration remains actionable.

## comment 5472623882 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5472623882

Created: 2026-08-31T01:35:17Z; updated: 2026-08-31T01:35:17Z

Exact metadata: [source record](sources/comment-5472623882-cfd57ff18fae7c1415b05442c6a468adc4e683b83348a995d9d62c89c9dd8cd4.json).

Removed the table-selection flicker path. Row selection now preserves the existing Table node and replaces only the adjacent Detail pane; it no longer rebuilds the list under the pointer. A rendered two-frame check confirmed the same Table node survives, exactly one row becomes selected, and the FF8/RDR2 panel layouts remain stable. The issue stays actionable for the remaining shared panel-geometry work.

## comment 5473087014 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473087014

Created: 2026-08-31T02:50:01Z; updated: 2026-08-31T02:50:01Z

Exact metadata: [source record](sources/comment-5473087014-491765b765caf4a1dfd26fa8df7341c0808fd0f08f69a91665c640e6c516afa0.json).

Blank Game was bypassing the shared panel composer with its own fixed CSS grid. It now uses the shared resizable layout, so its Table and Detail have the standard draggable divider, keyboard adjustment, persisted split, and right-click reset. The rendered Blank/FF8/RDR2 panel checks passed.

## comment 5473157861 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473157861

Created: 2026-08-31T03:02:07Z; updated: 2026-08-31T03:02:07Z

Exact metadata: [source record](sources/comment-5473157861-f189ff537754dd252a67c870ce9dc2717f90709e79df8af1bb99c2e69cb8485f.json).

Blank Game exposed two shared-theme leaks: the fallback palette was RDR-like, and the shared Detail heading used FF8 overlap geometry. Shared defaults are now neutral white/grey with an in-flow heading. FF8 keeps its menu palette and overlapping headings only in its own plugin. The rendered Blank, FF8, and RDR2 panel checks passed.

## comment 5473231566 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473231566

Created: 2026-08-31T03:13:42Z; updated: 2026-08-31T03:13:42Z

Exact metadata: [source record](sources/comment-5473231566-a3393490039433c0c038a56197ddcde94ea17de597c0a4d93d5880105dfff6de.json).

Blank Game is now the unthemed framework gallery. It has 1 Panel, 2 Panels, 3 Panels, and Subtabs pages showing shared fields, references, pins, sorting, hoverables, status tokens, and resize handles. Nested navigation now uses an exported shared subtab bar. Hidden renders confirmed panel/divider counts of 1/0, 2/1, 3/2, and 1/0; FF8 and RDR2 regressions passed.

## comment 5473291207 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473291207

Created: 2026-08-31T03:22:37Z; updated: 2026-08-31T03:22:37Z

Exact metadata: [source record](sources/comment-5473291207-0bcd1a8b9f5c0979c69c700cdd22092b256e407a845d60dba5bc643977d61b07.json).

Blank exposed that the shared Detail constructor did not apply the shared panel-surface class. Detail panels now receive the neutral fallback border and white surface automatically; games no longer need a local class to make them visible. The fresh Blank render shows the Detail panel against the grey page, and FF8/RDR2 panel regressions still pass.

## comment 5473538282 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473538282

Created: 2026-08-31T04:03:31Z; updated: 2026-08-31T04:03:31Z

Exact metadata: [source record](sources/comment-5473538282-860f85aa2925be9b4e1350cd577cb1cbc4b81323c2c17c5efc3f1bf6637f071d.json).

Blank now exercises the real shared Detail contract: a 20/80 header/body split, vertical type and range rails, bounded integer input, persistent edits, Boolean arrows and alignment, synchronized 38 px Save and Play controls, and distinct menu and tab surfaces. The rendered suite also passed FF8 and RDR2 regressions. Please restart Lexeditor and inspect Blank's 1 Panel and 2 Panels pages.

## comment 5473834036 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473834036

Created: 2026-08-31T04:44:15Z; updated: 2026-08-31T04:44:15Z

Exact metadata: [source record](sources/comment-5473834036-4f3b2a8c35660ca51e7ff64e161030cff75e05aa80a9b7ab43c126c6fadac899.json).

Blank's 1 Panel page now has 1-Ref Value through 4-Ref Value examples. Reference rails stack vertically and use fixed source colors: green Vanilla, then red, blue, and yellow for the three reference mods. The shared control rejects a fourth reference mod with a clear error. Hidden renders verified all four stack depths and the FF8/RDR2 panel regressions; please inspect Blank after restarting Lexeditor.

## comment 5473982847 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5473982847

Created: 2026-08-31T05:06:12Z; updated: 2026-08-31T05:06:12Z

Exact metadata: [source record](sources/comment-5473982847-5e4b2bb6a1267348390e476ce9a83cab94b7e9231eba347186d61f142fc21629.json).

FF8 nested sections and portrait subtabs now use one menu surface instead of slightly different overlays. Portraits have inter-item and top/bottom spacing. Checkboxes use the active plugin accent; green remains reserved for Vanilla true references and compact Boolean marks. The slashed pin now appears only while an active pin is being pressed, not on hover.

## comment 5474022153 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474022153

Created: 2026-08-31T05:11:53Z; updated: 2026-08-31T05:11:53Z

Exact metadata: [source record](sources/comment-5474022153-b6265f7ff023212422adb285c437e28c0602869f85a36325ff235377a50408de.json).

The shared Detail heading is now 15% instead of 20%. Read-only state no longer replaces the real data type: Blank's example shows STRING followed by a lock icon. Table headers are unaffected by the percentage; they remain content-sized with slightly larger bold text and reduced vertical padding. The rendered Blank, FF8, and RDR2 panel checks passed.

## comment 5474052703 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474052703

Created: 2026-08-31T05:15:53Z; updated: 2026-08-31T05:15:53Z

Exact metadata: [source record](sources/comment-5474052703-695e22986416613f35ebb79edeffba4562f68eee657305799df7d36ec3efcab6.json).

Fixed the recurring white native input in FF8 Magic > GF Compatibility. The cause was the compact control's extra wrapper, which put it outside the old direct-input theme selector. FF8 now themes every reference-backed non-Boolean input at the shared provenance-control boundary, including nested compact and unit controls. The rendered check confirms a dark field, white text, the FF8 bevel, and no box shadow; the complete FF8 UI render suite passes.

## comment 5474534716 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474534716

Created: 2026-08-31T06:19:48Z; updated: 2026-08-31T06:19:48Z

Exact metadata: [source record](sources/comment-5474534716-4ea385a41e28b696884ac9762e216a502d27f77ce048d54080f071394fdc8124.json).

Fixed the shared property type rail. Hovering the property and focusing its input now use the same outward slide. Left-column rails keep an internal gutter, so labels such as INT are no longer cut off; the min/max popup opens inward. FF8 numeric text controls now identify themselves as INT or FLOAT from their actual constraints instead of falling back to STRING. The rendered Blank, FF8, and RDR2 checks pass.

## comment 5474597191 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474597191

Created: 2026-08-31T06:27:01Z; updated: 2026-08-31T06:27:01Z

Exact metadata: [source record](sources/comment-5474597191-ea499ec306c21487a12c534e7c05531e392cb4e2a2c43404ab1968de0b5baac6.json).

Fixed Blank shared unit/reference alignment. The cause was reference padding on the unit wrapper, which ended the input border before the suffix, plus a fixed oversized reference lane. The suffix and reference now remain inside one continuous border, with a measured 3 px gap between units and V 25; the lane sizes from the configured reference values. The shared Blank/FF8/RDR2 panel suite and complete FF8 UI suite pass.

## comment 5474625087 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474625087

Created: 2026-08-31T06:30:02Z; updated: 2026-08-31T06:30:02Z

Exact metadata: [source record](sources/comment-5474625087-1e0cfdc528db8f3645c8d8d7348d5fbdf6cc17ba20576d32d37d821bd2451416.json).

Added the missing shared window-control inset. Blank now has a measured 6 px margin between Close and the right screen edge, matching the vertical breathing room around the 36 px controls in the 48 px command row. The shared Blank/FF8/RDR2 panel suite and complete FF8 UI suite pass.

## comment 5474735867 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474735867

Created: 2026-08-31T06:42:35Z; updated: 2026-08-31T06:42:35Z

Exact metadata: [source record](sources/comment-5474735867-b0c377c6f3832739490633ab8b699cf48d73852208fe6588f90da84c553d9778.json).

Reduced the shared Detail heading from 15% to 10%, leaving 90% for the body. FF8 Shops and Encounters had private 20/80 overrides, so those now use 10/90 too. Table headers are unchanged. Hidden Chromium measured Blank at 9.97% heading and 89.76% body; the shared Blank/FF8/RDR2 panel checks, FF8 current UI checks, and Shops fit checks pass.

## comment 5474768569 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474768569

Created: 2026-08-31T06:46:12Z; updated: 2026-08-31T06:46:12Z

Exact metadata: [source record](sources/comment-5474768569-1dfb8e00d3ec418407dc6f32530263388174f17f54b9fef5fcc34663dec6f3e5.json).

Fixed the graph point label. It is now centered on the mouse in the normal case and clamps by its measured width near either graph edge, so it cannot be cut off or leave the viewport. The far-right rendered check at 99.8% across the graph keeps the full label inside with a four-pixel inset. The curve contract and full FF8 UI render suite pass.

## comment 5474838079 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474838079

Created: 2026-08-31T06:54:26Z; updated: 2026-08-31T06:54:26Z

Exact metadata: [source record](sources/comment-5474838079-0aac4737f8088a9197f9b9ee3d253f1bf682bf5d29b45830d2582411078b069d.json).

Fixed the FF8 Character surface as a panel-level rule. The color mismatch came from restarting the same gradient on three nested elements: the physical toolbar, selector container, and portrait list. The selector and portrait list are now transparent, so only the outer framed panel draws the surface. I also removed FF8 detail-field subdivision borders, made the three Limit Break fields fill the row through its right edge, and kept each type rail inside its field track. The full FF8 rendered UI suite passes.

## comment 5474871299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474871299

Created: 2026-08-31T06:58:24Z; updated: 2026-08-31T06:58:24Z

Exact metadata: [source record](sources/comment-5474871299-4405716cc20662920d6bb96e58e50f0dd1edff58213e8a903b4263c98e76e0a1.json).

Fixed the FF8 heading-ID pin alignment against the actual selectable text. The old check compared the invisible button rectangle with the whole ID container; because the diagonal glyph's tip sits near the SVG's lower-left corner, it could pass while the visible tip was about 19 px too far left. The verifier now measures the SVG tip itself. It renders 3.14 px inside the ID text's right edge and 2.41 px below its top edge, with reserved overhang so it stays inside the panel. The full FF8 render suite passes.

## comment 5474934612 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474934612

Created: 2026-08-31T07:05:26Z; updated: 2026-08-31T07:05:26Z

Exact metadata: [source record](sources/comment-5474934612-3e6a1e8efb272bc9f6e81856b2f0e9f5fd88f3c95fc12108cd3c1bf29dbf6e12.json).

Fixed this at the shared internal-reference control. The graph drawer inherited a fixed right inset, and the visible reference stayed left-aligned inside its lane. Internal references now end at the input border. Hidden Chromium changed STR A, showed V26, and measured both right edges at 514.5625 px. The shared Blank panel suite and complete FF8 UI suite pass.

## comment 5474954711 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5474954711

Created: 2026-08-31T07:07:40Z; updated: 2026-08-31T07:07:40Z

Exact metadata: [source record](sources/comment-5474954711-51ad447d6facfc6a7ef230049747e52023e3a29a03ad96cb6a4a20aa10267a00.json).

Raised the shared FF8 Character/GF portrait-subtab hand from 38x26 to a true 2x size of 48x32. I moved its box left by the added width, so it keeps the same four-pixel overlap instead of covering more of the portrait. Hidden Chromium measured the final size and the complete FF8 render suite passes.

## comment 5482422807 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5482422807

Created: 2026-08-31T18:04:56Z; updated: 2026-08-31T18:04:56Z

Exact metadata: [source record](sources/comment-5482422807-cb615fd5b7468268e7ec829aee9d7e9ebcad7242862b81671da8adb9991084df.json).

Repaired the shared Detail and editable Table controls. Type rails are hidden until the whole property is hovered, stay visible while its control is focused, and change from the type to the bounded range on focus. Editable table cells now look like plain text until selected; the active input or dropdown fills the cell while its compact reference value overlays the right edge. Blank now exercises one-, two-, and three-panel layouts, editable integer/float/select fields, one- through four-source reference stacks, and Tweaks. The rendered Blank and FF8 panel checks pass.

## comment 5487148280 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5487148280

Created: 2026-09-01T01:19:45Z; updated: 2026-09-01T01:19:45Z

Exact metadata: [source record](sources/comment-5487148280-0ed2647856c5a53c5676daa0e40731fd43d91cf036b19e43d2d961d6f7fb5da0.json).

Repaired the shared controls exposed by Blank. Detail thumbnails now fill the usable 10% header slot and header IDs are vertically centered. Type and lock stay fixed on one axis; the range is a separate focus-only slide instead of replacing the type. Reference stacks overlay their lane and scale from one through four sources without changing row height. Internal suffixes collapse to the field edge when no reference is visible, move left only when needed, and enum references reserve the dropdown arrow. Blank detail pins are larger; the shared pin anchor now places the SVG tip 10% inward from an input/select corner and 10% outward from a checkbox corner. Editable Blank now uses the same persistent draggable columns as the base Table. The rendered Blank/FF8/RDR2 panel suite and shared Detail/Table contracts pass.

## comment 5487505946 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5487505946

Created: 2026-09-01T01:49:08Z; updated: 2026-09-01T01:49:08Z

Exact metadata: [source record](sources/comment-5487505946-dce4e196cd922aad3e9cfbf551f8cca300600c2a2997fdc0c07549eabfd63217.json).

Extended the shared panel contracts from this report. Blank Tweaks is now a separated special tab rather than an ordinary last tab. FF8 Item help markers participate in flag layout instead of covering labels, the price equation stays on one row, and the rendered shared-panel suite passes Blank, FF8, and RDR2 including three-panel divider movement.

## comment 5539024471 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5539024471

Created: 2026-09-04T10:16:26Z; updated: 2026-09-04T10:16:26Z

Exact metadata: [source record](sources/comment-5539024471-923ac85112cf9a7fc30c77994b68f17bb90b82d5877344ec112ca53af2626a84.json).

Shared fallback regressions to preserve in Blank: append representative FF8 tabs so new-game defaults exercise the repaired UI; property-type hover must expand around its center; multi-number needs a correctly rotated type rail and help control; sliders must be consistent; number handles need a much lower maximum opacity; all tables are editable by default; pin shadows need less spread; read-only locks need more size; Boolean and string reference values need fitted alignment; and tab labels must auto-fit around shortcut prompts. Panels must also enforce a minimum size that prevents clipped text.

## comment 5539253257 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5539253257

Created: 2026-09-04T10:38:39Z; updated: 2026-09-04T10:38:39Z

Exact metadata: [source record](sources/comment-5539253257-f8efae89e5a475de8f7959cd5c8838922bf483000449b1f771217fb1a847d2d5.json).

Feature freeze for triage. New shared-UI reports:

- Make the subtab bar two thirds of the main tab-bar height.
- FF8 subtabs must remain unboxed; plugin styling must not turn each subtab into a separate box.
- Hide Empty must have no surrounding box and must not clip the pager summary at the lower right.
- Blank should contain representative FF8-equivalent interface structures through shared defaults only. Do not copy FF8 theme overrides. The purpose is to prove that structural fixes carry into every new plugin.

Do not implement these changes until Lexer triages them.

## comment 5541450991 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5541450991

Created: 2026-09-04T13:54:12Z; updated: 2026-09-04T13:54:12Z

Exact metadata: [source record](sources/comment-5541450991-081f12d17c46b7a773871de9bbe5b16a5b369cfb01f56a6e3d30bc5a707dcfb0.json).

The property metadata defect was real. The shared code still stacked upright glyphs, and two FF8 Character overrides moved the rail into the property name. Type and range are now true 90-degree counter-clockwise words on stable parallel axes inside one shared left gutter. I also restored the missing Monogamy-to-Command Menu dependency arrow. The Blank and complete FF8 rendered checks pass. Restart Lexeditor before checking these source changes.

## comment 5541499184 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5541499184

Created: 2026-09-04T13:58:08Z; updated: 2026-09-04T13:58:08Z

Exact metadata: [source record](sources/comment-5541499184-8f00031225dca22daeee78eaf380af5e116b8a336a84f4512bfd2a8e93342b29.json).

Fixed the collapsed mod-selector status placement. The enabled check now owns a fixed right-side lane immediately before the dropdown chevron; the mod path ellipsizes before that lane instead of moving the check. The complete FF8 render measured clear separation and passed.

## comment 5549836584 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5549836584

Created: 2026-09-05T06:00:46Z; updated: 2026-09-05T06:00:46Z

Exact metadata: [source record](sources/comment-5549836584-ef0f63a15e6075a6df1f27277ab0b3a147182ed882bac63ddb20c0a5ee2ccf4b.json).

The RDR2 Effects and Behavior IDs tables now wrap names and IDs and reduce page capacity before text can be cut off. The detail controls also fit their panel. Hidden tests checked both views at 1600×900, then 1280×720, then the larger size again. Restart Lexeditor and inspect both Effects subtabs.

## comment 5549972479 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/46#issuecomment-5549972479

Created: 2026-09-05T06:27:54Z; updated: 2026-09-05T06:27:54Z

Exact metadata: [source record](sources/comment-5549972479-3ccf0b79f3e27628e805499d9431a2ec9c6347c9c713bd14a9b18a76fef9ae70.json).

Panel dividers now show a small two-column dot grip instead of a rounded scrollbar-like thumb. The resize area and controls are unchanged. Hidden checks confirmed the new grip and working keyboard resizing at two window sizes.
