# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5294824209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69

Created: 2026-08-30T22:57:10Z; updated: 2026-09-04T12:25:01Z

Exact metadata: [source record](sources/issue-5294824209-869a326366ae8b093bb60c7bac28cc50943fd4336174a154817ebbf7636f49ae.json).

Build and maintain the two installed Final Fantasy VII plugins without treating them as one product or copying FF8 schemas.

Current scope:

- Discover Steam app 3837340 as Final Fantasy VII and app 39140 as Final Fantasy VII (2013).
- Share the FF7 editor and data layer only where installed-file evidence proves the formats match.
- Decode the English KERNEL.BIN item, weapon, armor, accessory, and materia sections.
- Use the shared paged Table, Detail, search, project, save, and Vanilla-reference contracts.
- Validate bounded numeric fields and preserve every unknown record byte.
- Save a product-relative KERNEL.BIN copy under the selected mod project and reparse it before reporting success.
- Keep characters, enemies, encounters, shops, executable tweaks, and text writes visibly disabled until their schemas and deployment paths are proved.

Acceptance:

- Both installed products resolve their distinct KERNEL.BIN paths and decode the same 416 named English records.
- `/api/plugin` advertises `data-map`, `kernel-data`, and `save` for either identity.
- An edit changes only its documented bytes, saves atomically to the project, and survives binary readback.
- Invalid or unrepresentable numeric input is rejected.
- The rendered editor provides real sortable/paged/searchable tables, details, live Vanilla references, and accurate Data Map status without console errors.
- No installed game file is overwritten and no launched-game result is claimed before deployment and in-game validation.

## issue 5294824209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69

Created: 2026-08-30T22:57:10Z; updated: 2026-09-06T13:16:55Z

Exact metadata: [source record](sources/issue-5294824209-6916cc89873e766c4b1d7941d19ff9acd6e35a367c40056165a4de3ac73a55e5.json).

**Status: Closed for the initial plugin and KERNEL editing scope.** Both editions have separate detection/workspaces and shared supported equipment/materia editing with safe project saves. Broader character, enemy, encounter and shop work remains in #79; this was not full-editor completion.

## comment 5471818580 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5471818580

Created: 2026-08-30T23:05:29Z; updated: 2026-08-30T23:05:29Z

Exact metadata: [source record](sources/comment-5471818580-ef6e3681fe9ed0a0f87ec5e59762bd50965c9b33042b5e1b71f92cecec4aaab6.json).

The initial FF7 scaffold is implemented and rendered. It provides the managed FF7 service, shared themed shell, planned editor tabs, Info, and an 11-row Data Map. It advertises only scaffold/data-map support, disables saving, and clearly says no FF7 parser is connected. Check, smoke, syntax, rendered UI, and clean shutdown all passed.

## comment 5472059255 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5472059255

Created: 2026-08-30T23:56:46Z; updated: 2026-08-30T23:56:46Z

Exact metadata: [source record](sources/comment-5472059255-acb5ce0205de6ee32c8dba1268110020283ba6e12817ecb23ffebbee9e839713.json).

The FF7 scaffold targets the old Steam edition, so it cannot detect the installed current edition. The local Steam manifest identifies app 3837340 in FINAL FANTASY VII Steam Edition with FFVII_LAUNCHER.exe. I am replacing the stale discovery descriptor and adding an empty-config startup test that must find this installation automatically.

## comment 5472089396 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5472089396

Created: 2026-08-31T00:03:11Z; updated: 2026-08-31T00:03:11Z

Exact metadata: [source record](sources/comment-5472089396-6dc56adaa4f48223849a778bb151513152838a546a292aabd1fcb005dda69adf.json).

FF7 detection now targets the installed current Steam edition: app 3837340, FINAL FANTASY VII Steam Edition, and FFVII_LAUNCHER.exe. Starting from an empty Lexeditor config found the exact directory through Steam's manifest, validated and saved it, marked FF7 Ready, and opened the managed FF7 service. Parsing and saving remain intentionally unavailable in this scaffold.

## comment 5472167452 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5472167452

Created: 2026-08-31T00:16:17Z; updated: 2026-08-31T00:16:17Z

Exact metadata: [source record](sources/comment-5472167452-896152fae9959f28f1a4a5a9389c4747e4029b6634e11a4b3321cc60277674f6.json).

Product correction: Steam app 39140 and the new app 3837340 are separate FF7 products. The new release must not replace the legacy install descriptor. They should be separate plugin identities that share the same editor UI and data code where their formats match.

## comment 5472349118 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5472349118

Created: 2026-08-31T00:47:56Z; updated: 2026-08-31T00:47:56Z

Exact metadata: [source record](sources/comment-5472349118-fabbcbc58cf9aedd118a80b17a9c4d244a9e0aa2a9046ebd2205733e007e13eb.json).

Both installed FF7 products now have separate plugin identities and discovery rules. Steam app 3837340 uses FINAL FANTASY VII Steam Edition and FFVII_LAUNCHER.exe; app 39140 uses FINAL FANTASY VII and ff7_en.exe. Both were discovered from empty installation state and both checks and smokes passed. They still identify themselves as scaffolds and do not claim FF7 data editing.

## comment 5473639443 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5473639443

Created: 2026-08-31T04:17:04Z; updated: 2026-08-31T04:17:04Z

Exact metadata: [source record](sources/comment-5473639443-696aa2447b6868299ef69dd404a79b4a4d7a7c2d8273eb493ef3497b67e6dbc5.json).

The FF7 scaffold is now a real shared editor for both installed Steam products. It decodes 416 named records across Items, Weapons, Armor, Accessories, and Materia; uses bounded shared Detail controls with live Vanilla references; and writes an atomically verified project KERNEL.BIN while preserving unknown bytes. Binary tests passed on both product paths, and the hidden Edge edit/save/readback render passed without console errors. Characters, enemies, encounters, shops, tweaks, and text writes remain disabled because their writable paths are not yet proved. No project output has been deployed into either game, so launched-game behavior is still unverified.

## comment 5473688672 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5473688672

Created: 2026-08-31T04:23:18Z; updated: 2026-08-31T04:23:18Z

Exact metadata: [source record](sources/comment-5473688672-ebf0f06d5a87af6878a134e739c350db3aac81445aa4411b46a70ca7806388b4.json).

The separate 2013 identity now uses the real shared kernel editor too. Its readiness check requires both ff7_en.exe and data/lang-en/kernel/KERNEL.BIN; its managed smoke required the real data-map/kernel-data/save capabilities, decoded all 416 records, saved a bounded armor edit to the legacy project, and reopened it successfully. Both product checks and smokes, the binary contract, and the hidden rendered edit/save check pass.

## comment 5473787536 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/69#issuecomment-5473787536

Created: 2026-08-31T04:37:15Z; updated: 2026-08-31T04:37:15Z

Exact metadata: [source record](sources/comment-5473787536-480f5950ee1f41f7e4e8e71d5203091e6ea9cfe900ed2bf15e5c9a8e05d2d05a.json).

Both FF7 products now use the shared mod selector. First open creates a private baseline template and a default editable mod from that product's installed English KERNEL.BIN; New Mod clones that template, Find a Mod validates the exact product-relative kernel path, and switching restarts the editor on the selected project. New, find, switch, both product overlays, both plugin smokes, and the hidden shared-host selector render passed. Installed game files remain unchanged.
