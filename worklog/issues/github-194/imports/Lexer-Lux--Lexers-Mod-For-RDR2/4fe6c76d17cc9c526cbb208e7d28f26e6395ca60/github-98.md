# GitHub #98 - Per-icon ammunition counts

## Requirement

Every ammo icon in the focused weapon radial row needs its own live reserve
count beneath it. Zero-count entries need gray text and a dimmed icon, the stock
focused-entry counters need to disappear, and selection/layout input needs to
remain Rockstar-owned.

## Where it stands

The ASI half works and is confirmed in game. Lexer's screenshot on the issue
(build `9703EA02...`) shows correct per-icon numbers. His three remaining points:

1. the stock `X / Y` line is still on screen - **blocked, see below**;
2. the new text should use the stock font - **not reachable, see below**;
3. font size should be a dev setting - **done**.

## Attempt history

- The original DataBinding approach was disproved by its own log: every wheel
  opening recorded `wheel open; focused ammo binding list unavailable`. None of
  the guessed `quick_select`/UI-app roots exposed `focusedEntrySubSlotItems` to
  the ScriptHook thread.
- Replaced by `WHEEL_HIGHLIGHTED()` (`script.cpp:318`) plus
  `_GET_AMMO_TYPE_FOR_WEAPON` (`natives.h:8650`) to pick a compiled ammo row, and
  `GET_PED_AMMO_BY_TYPE` (`script.cpp:182`) per entry. That is what ships now.
- Two successive LML packages tried to hide the stock counter. Both were inert.

## The stock X / Y line: blocked, with evidence

`TXT_ItemCountIndicator` is confirmed as the `X / Y` node -
`UIText`, `<Style>WHEEL_SLOT_COUNTER</Style>`, `RawText` bound to
`focusedEntrySubSlotItemCounterText`, `Visible` bound to
`focusedEntrySubSlotItems.Size GREATER 1`, at
`_downloads/extract/radial_ammo_ui/quick_select_all/wheel_descriptions/sub_slot_list.ymt.rbf.xml:184-217`.
`ammoInTotal` appears three times in
`.../item_counters/ammo_counter.ymt.rbf.xml` (lines 62, 94, 111).

The binding-name substitutions in `RadialAmmoCounts/` are correct and
length-preserving. The **GamePath** is the failure:

- `install.xml` targets `update:/x64/data/ui/apps/0x24F69A6F.ymt` and
  `0x06A2E172.ymt`. Those are JOAAT of
  `hud/quick_select_all/item_counters/ammo_counter` and
  `hud/quick_select_all/wheel_descriptions/sub_slot_list` - verified arithmetic -
  but the premise behind them is not established.
- `codex/archive-extraction.md:20-22` records from testing that nested-archive
  entry names are hashed but that plain-JOAAT lookups fail, "so the scheme is not
  simple JOAAT". The install.xml premise contradicts settled codex truth.
- Deployment is not the variable. `ModManager.log:9-22` shows the package parsed
  and both resources registered; `lml/mods.xml` has it enabled and first in load
  order; a working ASI drew counts in the same session; the `X / Y` was still
  there. The mechanism executed and did not work.
- No reference on disk to copy. Every `<GamePath>` in `MyOverhaul/install.xml`
  and in the RDO, OCU, UCO, Kiddo and weapon-rebalance packages under
  `_downloads/` targets a flat archive path. The only `data/ui` target used by
  any of them is `update:/x64/data/ui/blipdata.ymt`. Nothing replaces a UI-app
  YMT.
- Getting the real key needs OpenIV. `_downloads/extract/update_2-keys.tsv` marks
  the nested `0x800AFF13.rpf` `Encrypted;`, and `codex/archive-extraction.md:24-36`
  records all four `Rpf8Extract` builds and both texture toolkits failing on it.
  The provenance of `_downloads/extract/radial_ammo_ui/` is unrecorded, so even
  the `hud/` prefix in the hashed paths is unverified.

The ASI cannot substitute. `DATABINDING::_DATABINDING_WRITE_DATA_*`
(`natives.h:1063-1072`) could in principle blank the counter text, but it needs
the same container root that the disproved read attempt could never resolve.

**Do not ship another guessed GamePath.** The next step is the real entry key,
not another hash.

## The font face: not reachable, no substitute invented

`_downloads/RDR2_SDK/SDK/inc/natives.h` exposes exactly five text-styling
natives: `SET_TEXT_SCALE` (:2206), `_SET_TEXT_COLOR` (:2207), `SET_TEXT_CENTRE`
(:2208), `SET_TEXT_DROPSHADOW` (:2211), `SET_TEXT_RENDER_ID` (:2212). A
case-insensitive search for "font" in that header returns nothing. The only font
native on disk is
`_downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/inc/natives.h:4178`
`NEXT_ONSCREEN_KEYBOARD_RESULT_WILL_DISPLAY_USING_THESE_FONTS`, which is the
on-screen keyboard. Zero hits across `_downloads/RDR2-Decompiled-Scripts/`.
The stock counter is not script text anyway - it is a UI-app node resolved
against `WHEEL_SLOT_COUNTER`. `SET_TEXT_FONT_FOR_CURRENT_COMMAND` was NOT used;
it has no definition anywhere in this repo and writing it would be exactly the
fabrication pattern in fuckups.txt.

## Ammo rows, re-derived rather than trusted

Read from `MyOverhaul/weapons.ymt` by splitting on `<Item type="CWeaponInfo">`
and taking the `<AmmoInfo>` sequence inside each `<DamageModes>` block. Confirmed
from `WEAPON_REVOLVER_CATTLEMAN` (weapons.ymt:51385-51493) and matched across the
whole file: exactly five multi-entry bullet signatures exist (revolver x14,
rifle x6, shotgun x6, pistol x4, repeater x4), each in the order
regular / high velocity / split point / express / explosive, with the four
shotgun loads, and `AMMO_22, AMMO_22_TRANQUILIZER` for the varmint rifle.

One correction found: `WEAPON_BOW`'s row has **twelve** entries, not six. The
trailing `AMMO_ARROW_TRACKING, _CONFUSION, _DISORIENT, _DRAIN, _TRAIL, _WOUND`
are Online ability arrows with no Story acquisition (`WEAPON_THROWING_KNIVES`
splits the same way). The module keeps the first six and flags this as the one
seat count that is a judgement, correctable live via `SeatCountArrow`.

Also noted, currently out of scope: dynamite, molotov, throwing knives and
tomahawk all have multi-entry rows and no family in the module.

## Changes this pass

`GameplayTweaks/modules/radial_ammo_counts.cpp`, rewritten:

- `loadSettings()` (:114-150) reads a new `[RadialAmmoCounts]` INI section using
  the fixed-point integer convention `fortification_hud.cpp:203-237` already
  uses. `TextScale` is Lexer's dev-settable font size.
- `log()` (:154-166) holds one handle for the session. The previous revision
  reopened the file once per printed token inside the count loop
  (old lines 157-165), which interleaved and could truncate a line mid-write.
- Idle heartbeat (:239-247) runs unconditionally before every early return, so a
  silent log now proves "not running".
- Per-render line (:292-307) prints the family, seat count, and every ammo type
  with its count, emitted on any change of weapon or of any count - so firing,
  buying, looting and crafting each produce a line.
- `seatCount()` (:201-206) applies `SeatCountArrow`; rows of fewer than two
  entries draw nothing (:261), because the wheel itself gates the sub-slot
  list on `Size GREATER 1` and there would be no icon row to annotate.
- `pixelX()` (:208-210) and `referenceCanvas()` (:168-180) are unchanged in
  method: scale by height against Rockstar's 1080 canvas, anchor at 0.5, so the
  run stays centred and unstretched on 16:9, 16:10 and ultrawide. `NudgeX/NudgeY`
  now offset the whole overlay.
- Text still draws with dropshadow only and no `DRAW_RECT` behind the glyphs, so
  the background stays transparent as the issue requires.

`GameplayTweaks/GameplayTweaks.ini`: new `[RadialAmmoCounts]` section after
`[RadialAmmoScroll]`, documenting that the font FACE is not settable and why.

`RadialAmmoCounts/README.md`: rewritten to record that the package does not take
effect and that its GamePaths are guesses. `install.xml` and the two RBF files
were left untouched - replacing one guessed hash with another is the exact
failure being documented.

## Not done

Not compiled, not linked, not installed. Static checks only.

## Runtime acceptance remaining

After a build and hash-verified install: revolver, pistol, repeater, rifle,
shotgun, varmint rifle and bow rows; live updates after firing/crafting/buying/
looting; zero-value tinting; mouse and controller cycling; alignment at the
user's resolutions and aspect ratios; and confirmation that the bow row shows six
icons rather than twelve.

## 2026-08-09 returned-test correction: disabled feature, square overlays, font

The latest installed INI still had `[RadialAmmoCounts] Enabled=0`, left over
from a crash bisect that had already cleared this module: the game still froze
with counts disabled. The screenshot therefore could not validate the current
count renderer. The project default is back to `Enabled=1` for the next build.

The visible large squares were not Rockstar UI. They were this module's
`DRAW_RECT` wash over every zero-count icon. That was a rectangular overlay, not
an icon tint, and it has been removed. Zero reserves retain gray count text; the
module no longer claims to tint an engine-owned icon it cannot address.

The earlier "font face is unreachable" conclusion ignored the working reference
linked on the issue. NativeMenu's `Drawing.cpp:253-283` supplies the complete
`TEXTFORMAT/P/FONT/~s~` script-text path, and `inc/enums.h:3-21` identifies
`FixedWidthNumbers` as **RDR Lino Numbers**. Count text now uses that face by
default through hot-reloaded `FontFace` and `FontSize` settings. `loadSettings`
was also corrected from one-shot loading to the documented two-second cadence;
the previous code falsely described its settings as live while reading them
only once per process.

`verify_radial_ammo_counts_issue_98.py` now rejects the square overlay, requires
the formatted RDR Lino Numbers path and real settings refresh, and no longer
portrays the empirically inert nested-archive GamePaths as proven. It passes.

The stock selected `X / Y` UI node is still unresolved because the LML
replacement's nested RPF entry key is unknown. These source/INI corrections have
not been built or installed yet so they cannot contaminate the installed crash
test. #98 stays `actionable`.
