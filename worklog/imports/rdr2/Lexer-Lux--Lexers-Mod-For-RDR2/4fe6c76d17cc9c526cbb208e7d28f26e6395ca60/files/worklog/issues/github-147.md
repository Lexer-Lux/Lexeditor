# GitHub #147 - Pocketwatch Rework

## Recurrence audit — bottom-right size-setting return

- **Primary evidence/reference:** the live owner comment dated 2026-08-10 says
  the clock must move to the bottom-right and its size must be editable in
  settings. `quickselectitems_ymt.xml` and `catalog_sp.ymt` remain the primary
  item evidence for `KIT_PLAYER_POCKETWATCH`; the resolved clock wrappers remain
  the time source. No position or size is inferred from an unrelated screenshot.
- **Sanctioned path:** retain the existing read-only ownership/time path, move
  only the authored HUD anchor, and read a bounded `[Pocketwatch] TextSize`
  value from the normal INI. Re-read it at a documented two-second cadence so
  both LEXEDITOR and the in-game settings menu save the same live value.
- **Execution proof:** the module heartbeat must report ownership, suppression,
  configured text size, and the two-second settings cadence. A changed size must
  emit a distinct settings log, so an unchanged screen can be separated from a
  module or reload path that never ran.
- **Rendered/player-visible acceptance:** static schema/API checks are not
  acceptance. This pass must render the same normalized right/bottom anchors
  and size-derived vertical formula at the default and at one larger supported
  size on a 1920x1080 reference canvas, then inspect both images for
  bottom-right anchoring, complete glyphs, and inward growth. The fixture uses a
  local serif surrogate because Rockstar's `$title` renderer is available only
  in-game; Lexer must still confirm its actual metrics after integration/install.
- **Per-frame mutation:** the only per-frame operation is the required
  frame-scoped `_DISPLAY_TEXT` draw while the owned-item and HUD gates pass.
  Inventory and setting reads remain bounded; the module never writes inventory
  or clock state.

## Live request read

- The issue body has no follow-up comments. It asks that once the player gets
  the pocket watch, the top-right of the screen continuously show the in-game
  time using the same visual language as the vanilla location/information text
  revealed with Alt.
- The attached image is a `395 x 73` crop referenced by GitHub. The attachment
  endpoint returned 404 outside GitHub's issue renderer; its role is also stated
  directly in the body as the vanilla Alt information-text reference.

## Authoritative item and clock path

- `_downloads/extract/radial_ammo_ui/quickselectitems_ymt.xml` places
  `KIT_PLAYER_POCKETWATCH` in the `KIT` radial slot. This is the functional
  player watch; the `PROVISION_POCKET_WATCH_*` records beside it are loot/fence
  valuables and are not used as the entitlement.
- The catalog record for `KIT_PLAYER_POCKETWATCH` identifies group `KIT`, model
  `S_INV_POCKETWATCH04X`, and its inventory/UI records.
- Existing resolved wrappers in `script.cpp` expose the Story clock through
  hashes `0xC82CF208C2B19199` (`GET_CLOCK_HOURS`) and `0x4E162231B823DBBF`
  (`GET_CLOCK_MINUTES`), and inventory count through `0xE787F05DFC977BDE`.

## Implemented

- Added `GameplayTweaks/modules/pocketwatch_time.cpp`.
- It polls ownership of `KIT_PLAYER_POCKETWATCH` once every two seconds. The
  inventory native is not called every frame.
- Once owned, it draws the live clock every HUD frame in the upper-right as
  `h:mm AM/PM`. Midnight and noon are normalized to `12`, and minutes are
  always zero-padded.
- The text uses the project's resolved complete RDR markup wrapper, `$title`
  face, warm off-white color, right alignment, and a restrained drop shadow to
  match the vanilla information-text treatment rather than a debug overlay.
- Drawing is suppressed while gameplay is locked, the screen is faded, the
  pause menu or HUD is hidden, or a cinematic camera is rendering.
- The module is read/draw-only: it never grants/removes the watch and never
  changes the game clock. State changes and a 30-second idle heartbeat make
  execution distinguishable from non-execution.
- No editor/schema or INI setting was added because the live issue specifies a
  fixed entitlement and presentation, not a user-configurable option.

## Integration handoff

- Include `modules/pocketwatch_time.cpp` after the shared inventory/clock/HUD
  wrappers are defined.
- Call `initializePocketwatchTime()` once during initialization.
- Call `updatePocketwatchTime(ped, now, locked)` once per frame, preferably in
  the existing HUD/render group. `now` is the existing monotonic `DWORD` tick
  and `locked` is the shared gameplay-lock state.
- No INI, editor, build-source, or release-manifest registration is required.

## Static validation

- `python tools/reverse-engineering/verify_pocketwatch_rework_issue_147.py`
- Scoped whitespace validation for the three issue-owned files.

## Runtime acceptance still required

- Before acquiring `KIT_PLAYER_POCKETWATCH`, confirm no custom clock appears.
- Acquire/own the functional pocket watch and confirm `h:mm AM/PM` appears in
  the upper-right within two seconds and advances with the Story clock.
- Confirm the style reads like the vanilla Alt location/information text and
  does not remain over pause, hidden-HUD, fade, or cinematic states.

## 2026-08-10 returned placement and size repair

- Re-read the latest owner comment before editing: the clock now belongs in the
  bottom-right, and its size must be editable through settings.
- Moved the readout to a fixed bottom-right safe-area anchor. The top coordinate
  is derived from the selected line height, so increasing size grows the text
  left/up rather than pushing glyphs off the bottom or right edge.
- Added `[Pocketwatch] TextSize=24`, validated to 12-64 reference pixels and
  hot-reloaded every two real seconds. Added its label, range, help text, and
  Pocket Watch settings group to `editor/settings_schema.json`.
- Added a deterministic 1920x1080 renderer for the exact right/bottom anchor.
  The default 24 px and larger 48 px outputs are stored under
  `worklog/issues/rendered/` and require visual inspection before handoff.
- Visually inspected both regenerated fixtures. In
  `github-147-default-24.png` and `github-147-large-48.png`, the complete time
  stays left of the 96% right-safe-area guide and above the 95.5% bottom guide;
  the 48 px sample grows left and upward with no clipped numerals or AM/PM.
  This proves the authored geometry and control direction, not Rockstar's
  in-game `$title` font metrics.
- Runtime acceptance still requires confirming the rendered font metrics and
  chosen safe-area anchor in RDR2 at Lexer's actual resolution, plus live size
  changes from LEXEDITOR/in-game settings after the fragment is integrated.
## 2026-08-10 installed release

- Included in release ASI `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
- The game-root ASI and required payloads were hash-verified. The open issue moved from actionable to test me; ownership, placement/style, clock advancement and suppression remain runtime acceptance.

## 2026-08-10 returned placement control

Lexer requested direct X/Y control instead of another guessed fixed anchor, and
explicitly requested the same for #148's temperature readout. The fixed clock
constants are replaced by hot-reloaded percentage coordinates. X is the
right-aligned text edge; Y is the text's top edge. The default values reproduce
the current authored placement, while 0..100 settings expose the full screen.
The temperature readout owns separate coordinates so moving either HUD element
cannot silently drag the other.
## 2026-08-10 returned test: horizontal position

The horizontal setting was converted backwards. Scaleform `RIGHTMARGIN` is a
distance inward from the right edge, but the module passed the requested screen
X percentage directly as that margin. PositionXPercent=100 therefore created
the largest margin instead of reaching the right edge. The conversion now uses
`100 - X`; 100 means zero right margin and smaller values move the clock left.
The same correction applies to the thermometer requested in the live comment.

## 2026-08-10 stale X value would have regressed with the fixed conversion

The previous entry corrected the horizontal conversion to `RIGHTMARGIN =
100 - PositionXPercent`. The saved settings still held `PositionXPercent=0`,
which was only meaningful under the old inverted conversion (0 then meant a
zero right margin, i.e. flush right). Under the corrected conversion the same 0
produces a full-width right margin and pushes the clock to the far left, so the
next installed build would have regressed the placement rather than fixed it.

Both the project and game-root INIs now use `PositionXPercent=95.8` and
`PositionYPercent=6.0`. That is the placement the issue asks for: the clock
shares the thermometer's right edge (#148 uses 95.8) and sits directly above it
at the top of the screen, instead of a new guessed anchor. Both values remain
hot-reloaded and directly editable, and the stale "anchored to the bottom-right
safe area" comment was corrected.

Placement is still runtime acceptance: the clock must read top-right at Lexer's
resolution without colliding with the thermometer or the compass.
