# #136: Separate trinket inventory view

[Live issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/136)

## Scope and presentation boundary

Provide a separate owned-trinket view. Do not claim a new native satchel category exists. The live issue asks for a concrete native-tab or separate-page proposal before choosing presentation.

## Current source evidence

Retained1491.50 satchel_ui_event_handler.ysc.c creates Satchel, Selected, satchel_menu_items, satchel_list_items and satchel_category_items. func_208 at0x87C7 populates categories through func_504; func_504 writes both UI data and the indexed Global_1935689.f_9418 category table. func_207 loops11 indices. Native category insertion must therefore prove the category-ID filter/selection behavior, available table capacity, focus and Back handling; a catalog category or standalone databinding append does not provide that proof.

Satchel.Collections is a different layer for player/saddle inventory collections. func_210 at0x8965 rejects a third collection (num>=2). It is not a spare trinket-tab list. Existing trinket/talisman effect handling elsewhere in the script does not add a category.

## Concrete proposal

Recommended route: a separate read-only page with only owned trinkets, selected name/effect details, owned count, keyboard selection and Back. Do not add equip, discard or activation controls to passive items. Use actual inventory quantities only for membership; never duplicate or change item storage. Preserve native satchel behavior.

Working interactive proposal: tools/prototypes/rdr2_trinkets/index.html. It is explicitly labeled as sample ownership/text and not an installed native tab. It includes owned/empty examples, case-insensitive search, arrow selection, focus and a Back request. The future runtime adapter must provide resolved trinket identities, localized text and current ownership; the proposal's symbolic sample IDs are not a complete live catalog resolver.

Headless check: tools/verify_rdr2_trinket_proposal.py passes owned-only filtering, unknown/zero counts, talisman exclusion, search, keyboard selection, empty view, Back request and no horizontal overflow at1200/600px. Render inspected. Screenshots: out/rdr2-trinket-proposal/trinkets-1200.png and trinkets-600.png.

## Remaining work

This remains source preparation, not a delivered in-game page. No existing satchel container, game file, save or active #151 recovery bundle was modified. Keep actionable while agent-side work remains.

## Native filter proof

The live body and every comment were read again. The actual 1491.50 population path is func_13 -> func_94 -> func_235 -> func_519. func_519 at0x12160 switches over known category IDs and returns false for an unknown ID. The new tools/verify_rdr2_satchel_category_dispatch.py compiles that exact retained function body with valid item/tag stubs. Known categories pass; three new IDs fail. A mutant that adds an invented dynamic fallback is rejected. The check also verifies the population call chain,11-index lookup and two-collection cap.

Thus adding a datastore category row alone cannot populate a new trinket category. This does not establish whether the authored movie can display/focus the extra row. A native-tab route needs a proven dispatcher patch as well as datastore capacity and movie/input checks; no such bytecode hook is available here.

## Native page preparation

Existing GameplayTweaks/modules/settings_menu.cpp provides a reusable native renderer: settingsMenuDrawText escapes markup and uses HUD literal text with the native body/title fonts; settingsMenuDrawSprite uses the same generic_textures/menu_textures dictionaries. Its settingsMenuPressed samples disabled frontend/game-menu controls. Existing overflow_storage.cpp demonstrates pre-emptive modal control suppression and entry/exit release gating. Neither file was changed for this issue.

New unregistered runtime source: GameplayTweaks/modules/trinket_view.h and trinket_view.cpp. The page accepts explicit catalog classification and localized display records plus a read-only count callback. It excludes zero/unknown counts, non-trinkets and duplicate identities; supports20+ records with seven visible rows, wrap selection, selected details and empty state. It uses the existing native renderer, rather than a new browser surface. frameTrinketView requires a full pre-emptive input blocker and disabled-input sampler, owns the entry-release and Back-release frames, and returns modal ownership to the dispatcher. No hotkey or dispatcher include was added, so this source cannot open a page in the current game.

tools/verify_rdr2_trinket_view.py compiles and executes both source files with fake native drawing/input/inventory. Passed: owned filtering, unavailable/zero counts, duplicate/talisman exclusion,20-row wrap/page/detail, empty view, denied modal entry, held entry press, held Back and release ownership, disable-before-sample, and unchanged inventory. Temporary compiler output is removed. This is execution proof for the adapter, not visual/game acceptance.

Before binding: supply verified complete catalog classification, current inventory counts, localized names/effects and measured text layout; define arbitration against native apps/settings/storage; select an explicit entry; validate actual keyboard/controller controls, glyphs, focus/Back, long names/effects and safe areas in game. The prepared renderer currently accepts caller-laid-out effect lines and shows at most five; it must not be treated as complete long-text support. Ownership is captured on entry; a refresh policy is still required if items can change while the page remains open. No inventory native failure semantics are inferred from the fake negative count test.

## Recurrence audit

Read C:/RDR2Mod/fuckups.txt and the module rules before preparation. Relevant prior failures: unsanctioned UI/native guesses, reacting to shared input before disabling it, permanent native writes fighting game state, and calling source/build proof visual acceptance. Primary evidence: retained1491.50 satchel filter and existing native settings renderer/modal input route. Execution proof: the actual predicate harness plus the unbound page harness above. Player-visible boundary: full in-game text, focus, controller, Back and inventory acceptance remain untested. The page performs no inventory writes and installs no native UI hooks.
