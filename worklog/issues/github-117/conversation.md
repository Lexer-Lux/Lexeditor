# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356287698 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117

Created: 2026-08-06T01:54:43Z; updated: 2026-09-05T06:55:41Z

Exact metadata: [source record](sources/issue-5356287698-7ed5fc0c872aa55c3ebbab1787901c919b6225a106a76671fb44dff30c1b2787.json).

SETTINGS PAGE REWORK — human-readable names, units, checkboxes, columns.
     Your words, kept whole:
     "Instead of vague .ini setting names, give everything in the settings page a
     clear, human readable name and a unit to be shown after the amount (for
     numerical settings). Instead of just one longass column of settings we can
     have like 3 or more so it's not this insanely long hard to navigate page. IG
     each subsection should be its own column? Oh, and instead of making me type
     in true or false or 0 or 1 (but allowing higher values???) boolean settings
     should just be a checkbox. Obivously. Here's how I want the settings page
     laid out. If I don't describe what should happen to a setting, don't delete
     it. Leave it where it was."
     MAP
       - Each category toggle goes here. Remove the global "Enable". Players can
         just disable them all for the same effect.
       - Train markers toggle goes here too
       - Auto Clear On Reach
       - Auto Clear Distance
     MISC
       - Animal Density Multiplier (remove the toggle. they can just make it 1x
         if they want to disable it)
       - Hunter Hatchet Rework
       - Recoverable Unique Weapons
       - Mask Carrying Rework
       - Holstering Actually Holsters
       - Sell Only Duplicate Cigarette Cards
       - Remove the partial bounty repayment stuff. No reason to disable such a
         great feature.
     DEV
       - Campsite Key
       - RespawnWindowMS
## Setting lifecycle tags

Every setting must visibly state when it can take effect:

- Keep the existing blue `DEV` tag for developer-only settings.
- Add a red `CONST` tag to every setting that cannot be hot-reloaded.
- A `CONST` setting must not look equivalent to an immediately applied setting.
- The setting help/tooltip must state its exact application boundary: game restart, ASI restart/reload, data rebuild plus restart, or another required action.
- Determine lifecycle from the actual reader/application path, not from assumptions or naming.
- Settings that are genuinely polled/re-read while running remain untagged unless another existing tag applies.
- Tags may coexist when appropriate; for example, a developer-only setting that also requires restart may show both blue `DEV` and red `CONST`.
- Use the same tag colors and meaning consistently across categories and search/filter results.

## Acceptance additions

1. Audit every exposed setting and classify its real reload behavior.
2. Confirm every non-hot-reloadable setting shows the red `CONST` tag.
3. Confirm hot-reloadable settings are not falsely tagged `CONST`.
4. Confirm blue `DEV` tags remain intact and can coexist with `CONST`.
5. Confirm help text tells the player exactly what action is required for each `CONST` setting to apply.

## issue 5356287698 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117

Created: 2026-08-06T01:54:43Z; updated: 2026-09-06T13:17:10Z

Exact metadata: [source record](sources/issue-5356287698-a0f3b367b0f90498c5db4f8ca52e615fe3e54ed51f89b03e89143b67d1ece874.json).

**Status: Closed after the settings-editor rework.** Settings use human-readable names, units and suitable controls in responsive categories. DEV marks developer-only options; CONST and its help explain when a restart or rebuild is required. Unspecified settings are preserved.

## comment 5550113806 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113806

Created: 2026-08-06T05:20:10Z; updated: 2026-08-06T05:20:10Z

Exact metadata: [source record](sources/comment-5550113806-06129bc0ac2a7ce56e7096087808410c482cff6a6a97ab13a2bd35a46f4d489f.json).

Implemented and static/API validated. Reload LEXEDITOR and test the responsive MAP/MISC/DEV settings cards, human-readable labels/units, boolean checkboxes, preservation of unspecified settings, Campsite Key text input, and save/reload behavior. Partial bounty is now always on and its obsolete controls are removed.

## comment 5550113820 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113820

Created: 2026-08-06T09:50:09Z; updated: 2026-08-06T09:50:09Z

Exact metadata: [source record](sources/comment-5550113820-a2dcf1ad128405c74ccab6f8b36379755813703d14bad6ecbfb532d296eea7de.json).

big improvement, i love it, but the ? things shouldn't be on seperate rows than the setting text itself, enabled check marks don't need the text "enabled" describing that they're enabled (????? why) and there seem to be no subcategories? you could like, make every category a big horizontal bar segemnting the page vertically, or just big 3-column-wide things, or whatever, but it seems like you didn't do the subcategories at all?

## comment 5550113831 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113831

Created: 2026-08-06T11:58:42Z; updated: 2026-08-06T11:58:42Z

Exact metadata: [source record](sources/comment-5550113831-08cc725e3c0d2ccfddc5a50578cac561db4de4393155442a13f459268261b122.json).

okay the "enabled" text is still there but it doesn't actually seem to reflect whether or not the tick box is enabled or not. it seems to be a location or adress or whatever so just keep it?
i still don't see the subsections?
question marks are fixed though

## comment 5550113839 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113839

Created: 2026-08-06T13:10:45Z; updated: 2026-08-06T13:10:45Z

Exact metadata: [source record](sources/comment-5550113839-20918c4058aeef5415ae92adf85f4a73bb1ae10c78f8c27946300e3c0b852210.json).

you didn't do anything.

## comment 5550113851 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113851

Created: 2026-08-06T14:10:08Z; updated: 2026-08-06T14:10:08Z

Exact metadata: [source record](sources/comment-5550113851-fe091b34eaa77740b83d013345758baeb7219ef2d80b43fb2cea34e0e847af84.json).

The settings-page rework is live in the running LEXEDITOR server: full-width horizontal category bars, responsive 3/2/1-column setting grids, inline help, and preserved Section/Key plus /Enabled technical controls. Static verification covers all 45 sections and 286 current settings. Refresh the editor page and verify layout, help, and editing at your normal window size.

## comment 5550113872 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113872

Created: 2026-08-06T14:35:23Z; updated: 2026-08-06T14:39:31Z

Exact metadata: [source record](sources/comment-5550113872-38f903ed5b865fde9f86d1fb03eb825e9aee834616fd636e1d935fb7825ed22c.json).

??????????? now there are big horizontal separators for main categories instead of boxes. okay, but there are still no subcategories
do you not understand what "subcategory" means? do you not understand what subcategories I want? what is the issue here? each subcategory should have its own column within the main category.

actually, no more developer section. instead, individual settings should be tagged as developer, displayed with a different background color in the editor and in-game settings, and hidden in the in-game settings with devmode off.

this page is full of settings with unclear names and no ? explainer.

bullet tracer mode should not be free-entry. wtf? it should be a dropdown.

tracer-related settings should get their own section.
human stamina and horse stamina should be subsections under stamina.
core xp gain goes under misc.
why is there a seperate collectible map section when we already have a map section?
collectible probe is a dev setting, goes under map.
Lost money section should be renamed to bloodstain.
why is there a map icon setting. there's no reason for the user to be changing this.
ditto for prop model.
there should bea setting for the amount of stamina consumed when doing a combat roll.

we should have two section columns next to each other, not one.

horse persistence goes under Miscellaneous section.

auto-bank should be a boolean it seems? why is it a number? also it should be categorized with the wallet options

## comment 5550113892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113892

Created: 2026-08-07T08:32:58Z; updated: 2026-08-07T08:32:58Z

Exact metadata: [source record](sources/comment-5550113892-4a9d53eeef3d81118ba197a0d67f7ebdd8f6ca8a17119a13c9973b208b7c0579.json).

create a unique items rework category. hunter hatchet and recoverable uniques should go in there. 
duplicate cigarette cards -- what is this? the name is incoherent. the description is incoherent too. if this is the feature where you can only sell cigarette cards once you've handed in their set to that guy then wow, you desrcibed it horribly. if that's the case then give it a name like "Cigarette Card Sell Safety" and add it to misc.
train markers toggle should be with the other map toggles. did i not ask for that already
collectible probe should be a dev setting.
remove all the logging toggle settings seeing as we're combining all the logs anyway
why is "fence reversed" a numerical field? and the collectible map toggles -- actually, wtf? It seems like almost every single thing that should be a boolean toggle you went and changed to numerical. wtf? why?

in the future be cognizant of this category/subcategory system and add new settings appropriately.
dev settings appear the exact same color in LEXEDITOR, or maybe they're just not being marked correctly. 

## comment 5550113904 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113904

Created: 2026-08-09T07:01:13Z; updated: 2026-08-09T07:01:13Z

Exact metadata: [source record](sources/comment-5550113904-32a5103008b70c80292e9645de2e7815278c7a44082042be89c953b2f81700f6.json).

Corrected the remaining Lexer-Lux/Lexeditor#117 items against the latest comment:

- Map now groups Train Markers with the collectible marker toggles.
- Added a separate Unique Items Rework category for Hunter Hatchet and Recoverable Unique Weapons.
- Renamed/described the real mailed-set behavior as Cigarette Card Sell Safety.
- Fixed the missing boolean declarations (including Gang Hideouts, Auto-Bank, tracer-only, and recon layer switches).
- Removed logging-toggle controls from both settings UIs while leaving the unified GameplayTweaks.log automatic.
- Developer rows are now visibly purple/DEV-tagged in LEXEDITOR; the in-game menu hides them with dev mode off and distinguishes them when on.
- Added a real CombatRoll StaminaCost runtime setting, charged once after the authored roll starts with before/after trace readback.
- Updated the radial-count settings schema to the current FontFace/FontSize keys.

Static verifier, inline JavaScript syntax, server compile, API schema readback, and the development ASI build pass. LEXEDITOR is restarted on port 8765, so refresh it to see the editor changes.

I did not install this newer gameplay binary over the recon-crash candidate currently under test. Lexer-Lux/Lexeditor#117 therefore remains actionable; no label was changed.

## comment 5550113915 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113915

Created: 2026-08-09T07:19:07Z; updated: 2026-08-09T07:19:07Z

Exact metadata: [source record](sources/comment-5550113915-d7731719ffd911e4bf095b45cbe611d2ea5d7e4ba9d3d3b0a8b843db99b5e4c6.json).

The gameplay-side settings changes are now installed and hash-verified in development ASI BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5; the matching INI is installed and LEXEDITOR is live on port 8765. Refresh LEXEDITOR, then test the new categories/checkboxes/dev styling plus Combat Roll Stamina Cost. Moved from actionable to test me and read back OPEN with only test me.

## comment 5550113929 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113929

Created: 2026-08-09T09:39:45Z; updated: 2026-08-09T09:39:45Z

Exact metadata: [source record](sources/comment-5550113929-b32847837f835783941eb3375f730c1a830018a4fbedb46060595a3ab6aed766.json).

Pause map zoom speed into minimap subcategory. Rename to map. Rename marker toggles to map icons. marker cleanup and devtools subcategories go into new dev tools subcategories.
"Hold MS" rename "Hold Time"
Draw MS, Stow MS go into Binoculars>Dev Tools subcategory
what are these equip p 3, 4, 5 settings? do we need them? if not remove them
Recon Tagging appears bugged. each column has...two columns inside it? wtf?
Stamina>Wagon Team rename to "Vehicle Stamina"
Stamina>Reserves subcategory should be moved into Cores
Tracers doesn't need subcategories. Just make the "Vanilla Bullet Tracers Only

<img width="86" height="63" alt="Image" src="https://github.com/user-attachments/assets/8503fa4d-2522-4417-9c26-46b123b23d8f" />
Sometimes for these number input boxes you can clearly see part of the number is cut off on the right side and when i mouse over i can see the up/down clicker buttons which seems to be the reason?

weapon ammo caps should not be for all the ammo. remember there are only 4 firearm round types in my game. check the game data. 3 cartridge calibers and shotguns, plus arrows. you're using ALL of the ammo types from vanilla and their vanilla names.

i don't understand base drain hours under temperature because aren't we already setting our drain time in the core clock subcategory? or is this just really poorly phrased? i don't understand what this does.

" toggle into a simple Enable toggle that enables/disables our new custom tracers.
Why is carried mask items still a setting? Isn't this an internal game-state variable, not something we want players freely editing? ESPECIALLY when this is a free-input text box -- couldn't they brick their whole game this way?

## comment 5550113941 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113941

Created: 2026-08-09T11:07:05Z; updated: 2026-08-09T11:07:05Z

Exact metadata: [source record](sources/comment-5550113941-93edbbc887561443b380f2a76f40a011ca402cafb60201c38e690d37fa3896d7.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53 with the current INI/schema. Dead binocular flags and the inverse tracer switch are gone; ammo caps use the overhaul caliber pools; categories, developer fields, nested layout, numeric clipping, and server-side range clamping were corrected. Test the reorganized GameplayTweaks settings page and live-save controls.

## comment 5550113952 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113952

Created: 2026-08-10T07:17:28Z; updated: 2026-08-10T07:17:28Z

Exact metadata: [source record](sources/comment-5550113952-aad357caf31329f46bcccea2fc6ed7ec22123890679b0ccfee23325aab021cca.json).

Fixed the settings `?` tooltip fallback reported on 2026-08-10.

- Field help no longer falls back to the full INI section introduction. Section text stays on the category heading.
- A field without authored help gets a short setting-specific fallback.
- Dead Eye Drain Rate now says: "How many outer Dead Eye bar points are drained per real second while Dead Eye is active. 0 keeps the vanilla drain rate."
- Both Lexer-Lux/Lexeditor#117 settings verifiers, Python compilation, JSON parsing, `git diff --check`, and the live `/api/settings` response passed.

The issue remains open with its existing `test me` label.

## comment 5550113969 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113969

Created: 2026-08-10T07:50:58Z; updated: 2026-08-10T07:50:58Z

Exact metadata: [source record](sources/comment-5550113969-1366dfb4cc1e591bf27fb62abcf63b0019f5bf019627dc3ce8b0c5bb11b929a1.json).

<img width="405" height="202" alt="Image" src="https://github.com/user-attachments/assets/385ed63b-25f8-4a5d-8246-9f8a0eb6ca30" />
numbers still cut off

## comment 5550113980 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113980

Created: 2026-08-10T10:23:59Z; updated: 2026-08-10T10:23:59Z

Exact metadata: [source record](sources/comment-5550113980-1eb157c500f04e9096cb3ebb34e029fc3220e4de6db5d36f78277ddc5f0fa97a.json).

New requested settings UX: retain blue DEV tags and add red CONST tags to every setting that cannot hot-reload. Each CONST setting must state its exact apply requirement (restart, reload, data rebuild, etc.), based on the actual code path. This is new work, so Lexer-Lux/Lexeditor#117 is correctly back to actionable.

## comment 5550113996 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550113996

Created: 2026-08-10T11:02:45Z; updated: 2026-08-10T11:02:45Z

Exact metadata: [source record](sources/comment-5550113996-8747d6801a59a78744182344aef45abffd74bb015a99acb29ca3ad98139105f7.json).

Implementation update (not yet built/installed): all 352 currently exposed settings were audited against their actual reader paths. 312 genuinely hot-reloadable settings remain untagged; 40 non-hot settings now receive a red CONST chip with the exact apply boundary in help. Existing blue DEV chips remain, and five settings correctly show both DEV and CONST. JSON, extracted JavaScript, API-schema, and all Lexer-Lux/Lexeditor#117 verifiers pass. Lexer-Lux/Lexeditor#117 remains actionable until the editor files are installed and visually checked.

## comment 5550114016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114016

Created: 2026-08-10T11:15:29Z; updated: 2026-08-10T11:15:29Z

Exact metadata: [source record](sources/comment-5550114016-510740f0a5681740c81d88c00f043f1faa9d43a4c16607803ae1a761c9b7f711.json).

Lifecycle audit correction after Lexer-Lux/Lexeditor#238 integration: the new `[CoreCostGuard] Enabled` toggle is hot-reloaded on a bounded two-second cadence, so the current audit is 353 exposed settings: 313 live/untagged and 40 red `CONST`. The removed Lexer-Lux/Lexeditor#201 child-hook setting remains present only for compatibility and is now correctly described as `CONST — no action applies in the current build`, rather than promising that a restart will install or remove hooks. All Lexer-Lux/Lexeditor#117 lifecycle/editor verifiers pass with those current totals.

## comment 5550114030 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114030

Created: 2026-08-10T12:30:17Z; updated: 2026-08-10T12:30:17Z

Exact metadata: [source record](sources/comment-5550114030-f80703ad44f370700aa6d1a68bd4774061de108cc4edac0bdf0d427d60daff57.json).

<img width="1659" height="240" alt="Image" src="https://github.com/user-attachments/assets/ec451ffc-34db-4b86-bf70-0bacf862888d" />

? again with the inconsistency. why dev settings colored all the way through (good) while const settings only get this tiny box

## comment 5550114044 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114044

Created: 2026-08-10T13:03:38Z; updated: 2026-08-10T13:03:38Z

Exact metadata: [source record](sources/comment-5550114044-8d94899f761ca1ac989430c8bf88bece8ee0c6c89cd30b8133d40da8861be630.json).

CONST rows now use the same full-row treatment as DEV rows: red across the whole setting, purple across DEV, and split purple/red when both apply. I rendered the real Settings page at wide and narrow widths; all 354 visible settings are present, 40 CONST rows and 18 DEV rows are styled consistently, the five mixed rows show both states, and the narrow layout has no overflow. Refresh LEXEDITOR and inspect Settings.

## comment 5550114055 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114055

Created: 2026-08-10T15:26:40Z; updated: 2026-08-10T15:26:40Z

Exact metadata: [source record](sources/comment-5550114055-16c255ec2cc4ee599f8057f36c6e07cbeaaf043a9e26af79f81bb92f4857c17b.json).

Dev should be blue, not purple.
Things that are dev + const should then be purple since it's blue + red.
Child vulnerability should be under misc. Did I not tell you to keep the existing categories in mind when adding settings now?

## comment 5550114068 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114068

Created: 2026-08-10T17:00:46Z; updated: 2026-08-10T17:00:46Z

Exact metadata: [source record](sources/comment-5550114068-0262fcf26d191b8b3e90adddaf80c1387a9c6f74b7c00ab508e3a9be9449fa89.json).

The corrected settings UI is ready to test. DEV rows are blue, CONST rows red, DEV+CONST rows purple; Child Vulnerability is under Miscellaneous / Gameplay. The editor and generated in-game menu now expose the same 359 visible settings, including both road-speed multipliers. Refresh LEXEDITOR and check wide/narrow Settings; in game, check right-side placement and one saved boolean/numeric edit.

## comment 5550114082 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114082

Created: 2026-08-11T04:02:24Z; updated: 2026-08-11T04:02:24Z

Exact metadata: [source record](sources/comment-5550114082-2ca96a8ab69032aebc2ed6ab0404c5cd577c7b77439fafe08c9c0e8b2d9c9422.json).

The settings are FULL of numerical settings that I'm pretty sure should be booleans. Unless I'm mistaken. Vehicle low camera, crouched aim low camera, lock to one third person zoom mounted, disable horse camera centering. And others. PLease fix all these.

## comment 5550114092 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114092

Created: 2026-08-12T13:50:35Z; updated: 2026-08-12T13:50:35Z

Exact metadata: [source record](sources/comment-5550114092-1f7cda73b3fc8703d0a31d36a3a154899fcc9c7a212be06bf0172c31715603df.json).

I restored compact horizontal Settings rows. The name, DEV/CONST badges, help, and INI section/key now stay on the left; the value and unit stay on the right. Boolean rows use the same compact layout. I also removed the developer-settings visibility checkbox, so developer rows are always shown. Fresh wide and narrow renders contain all 357 settings with no clipped inputs or page overflow. Refresh LEXEDITOR to check the result.

## comment 5550114106 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/117#issuecomment-5550114106

Created: 2026-08-13T08:48:52Z; updated: 2026-08-13T08:48:52Z

Exact metadata: [source record](sources/comment-5550114106-18d1f7911f844503222e2adb6fd3018f246c644e534478d21c9d07b7e4ad5522.json).

The live LEXEDITOR test passed at normal and 390-pixel widths. All 359 settings loaded; boolean values use checkboxes, numeric values keep their units, DEV rows are always present, lifecycle colors and mixed DEV+CONST rows remain visible, and the compact label/value rows stay aligned without horizontal overflow or clipped controls. The browser console had no warnings or errors.
