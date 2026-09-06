# GitHub #143 — binocular mask restoration

## Returned failure

The supplied 2560x1440 screenshot showed a black single-circle aperture with a
visibly stair-stepped edge. At `MaskScale=1` and `MaskOpacity=1`, this did not
match the ordinary opaque vanilla binocular mask requested by the issue.

## Root cause and repair

`GameplayTweaks/modules/binocular_optics.cpp` was painting a second mask over
the engine view. It approximated one circular inner edge using only 32
horizontal `DRAW_RECT` bands. Each band was 45 screen pixels high at 1440p, so
the large steps in the screenshot were the authored geometry, not texture
filtering. A one-circle equation also could not reproduce Rockstar's binocular
silhouette at any resolution.

The regular Story binocular component already names the authoritative native
presentation: model `w_binocular_inner01`, post-FX stack `ScopeBinoculars`, and
vanilla `LookingGlassScale=1.000000` in
`_downloads/extract/update_1_common/common/packs/base/data/ai/weaponcomponents.meta`.
The ASI rectangle overlay was removed, and the regular component's scale in
`MyOverhaul/weaponcomponents.meta` was restored from the earlier `0.900000`
experiment to the native `1.000000`. FOV tuning and the optional diagnostic
zoom readout are unchanged.

`tools/reverse-engineering/verify_binocular_mask_issue_143.py` compares the
current regular component with those three primary-source native fields and
rejects the old rectangle/band implementation. The existing #59 verifier was
updated to require the restored native scale and absence of `DRAW_RECT`.

No build, install, game launch, INI, shared dispatcher, release manifest, or
GitHub label was changed. Player-visible acceptance still requires opening the
regular Story binoculars and confirming that the engine-rendered mask is the
smooth vanilla silhouette at the default settings.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- The custom rectangle mask was never a valid approximation: 32 bands visibly stair-stepped at 1440p, and removing it without restoring Rockstar's own mask produced the user's latest failure.
- The candidate restores the primary-source vanilla binocular component/model and native `LookingGlassScale=1.0`; acceptance is the actual smooth binocular silhouette in Story binocular view, not metadata or archive presence.

## 2026-08-10 recurrence audit before the missing-mask repair

- **Primary evidence/reference:** the supplied 2560x1440 screenshot proves the
  rejected rectangle overlay was a pixelated single circle; the three latest
  live comments prove that removing it left no mask at all. The local vanilla
  `weaponcomponents.meta`, Story `binoculars.c`, the actual regular-binocular
  component selected by the equipped kit, and any supplied mask/model assets
  are authoritative. Merely finding `w_binocular_inner01`, `ScopeBinoculars`,
  or `LookingGlassScale=1` in a data record is not execution or presentation
  proof.
- **Sanctioned path:** restore Rockstar's own binocular-shaped model/post-FX
  through the exact component and Story weapon path the live regular binocular
  kit uses. Do not redraw a circle from rectangles, invent a texture name, or
  add a second mask over an already-correct native silhouette. Explicitly
  reconcile the regular and improved component records and #4's selected kit.
- **Execution proof:** static evidence must identify the exact equipped weapon,
  component hash, model, post-FX stack, and scale from primary data. Bounded
  runtime logging must identify regular/improved kit and true optics-ready
  entry. Native metadata presence alone remains insufficient; there is no
  available ASI readback for “mask pixels rendered.”
- **Player-visible acceptance:** at opacity/scale 1, regular quick-access and
  ordinary satchel binocular use show the smooth opaque vanilla two-lens
  silhouette at 2560x1440; improved optics retain their intended distinct FOV
  without deleting the mask. No single circle, stair steps, or maskless full
  screen is acceptable.
- **Every per-frame native:** no per-frame geometry reconstruction or mask
  setter is sanctioned. The optics module may log bounded zoom/kit state, while
  Rockstar's component/post-FX path owns rendering. Any ASI fallback would need
  a proven asset and state transition, not per-frame speculative rectangles.

## Returned-test repair: explicit native component-scaleform lifecycle

The data path was already correctly linked: Story
`WEAPON_KIT_BINOCULARS/LookingGlassDefaultScopeInfo` selects
`COMPONENT_BINOCULARS_SCOPE01`, whose current record retains
`w_binocular_inner01`, `LookingGlassScale=1.000000`, and `ScopeBinoculars`.
Therefore copying the same metadata again could not repair the reported absent
presentation. #4 also deliberately selects the regular Story kit, not the
Story-incompatible imported improved hash.

The local native database and ScriptHook header resolve a supported runtime
lifecycle that the previous removal omitted. More importantly, the shipped
Story scripts call the exact pair: `sean1.c:70285/70399` and
`odriscolls1.c:78123/78181` open and close the component scaleform:

- `GRAPHICS::_0x21F00E08CBB5F37B("COMPONENT_BINOCULARS_SCOPE01")` triggers the
  binocular scaleform and is documented from Rockstar SP script use;
- `GRAPHICS::_0x5AC6E0FA028369DE()` closes that scaleform.

The optics module now issues the trigger once on the rising edge of the exact
regular-kit plus first-person-aim gate. Ordinary wheel use accepts Rockstar's
camera readback directly; while #4 quick access owns the draw, the additional
`g_binocularsActive` publication prevents the scaleform from appearing before
the optics reach Arthur's face. It issues the matching close once when optics
leave or mask presentation is disabled. It does
not redraw geometry, reissue the trigger every frame, or alter the regular and
improved component data. Bounded logs distinguish trigger attempted, active
heartbeat, and close attempted. The native exposes no presentation readback,
so every line says `readback=unavailable` instead of claiming pixels rendered.

Static verification was assigned to
`tools/reverse-engineering/verify_binocular_mask_issue_143.py`. Runtime
acceptance is still the supplied-reference comparison at 2560x1440: ordinary
wheel use and #4 quick access must show the smooth opaque vanilla binocular
silhouette only after the optics are ready, with no pre-draw overlay, missing
mask, single circle, or stair steps. Trigger logs alone are not acceptance.

## Returned-test correction: measured two-lens raster

The mission-scaleform repair executed and failed. The live combined log recorded
ten separate `#143 native mask trigger requested` entries, followed by mask
close entries, while the player still saw no mask. That execution evidence
closed the native-trigger path; it was not kept as a fallback. The two cited
Story uses were mission camera sequences, not proof that the native owns the
ordinary player binocular presentation.

Before the replacement, the recurrence check named these boundaries:

- **Primary data:** the regular component still used
  `w_binocular_inner01`, native `LookingGlassScale=1`, and
  `ScopeBinoculars` in Rockstar's extracted `weaponcomponents.meta`.
- **Executed failure:** the live log proved the mission-scaleform native ran;
  the player's visible result proved it did not draw the free-roam mask.
- **Visual reference:** the 1920x1080 vanilla capture at
  `https://interfaceingame.com/wp-content/uploads/red-dead-redemption-2/red-dead-redemption-2-binocular.jpg`
  supplied the two-lens outside edge. Fits from brightness thresholds 35 to 60
  stayed within about seven pixels. The midpoint fit used left centre
  `(666.86, 534.12)`, radius `(530.07, 517.30)`, with a horizontal mirror for
  the right lens.
- **Sanctioned render path:** the already-proven streamed-TXD plus
  `DRAW_SPRITE` HUD path now draws one persistent raster while the verified
  optics camera is up. A HUD element must be drawn each frame. No per-frame
  setter fights engine state.
- **Player-visible boundary:** at `MaskScale=1` and `MaskOpacity=1`, the result
  must be the smooth opaque two-lens silhouette at 2560x1440. Larger scale must
  expose more of the screen; lower opacity must make the same edge translucent.

`GameplayTweaks/binocular_mask/build_mask.py` supersampled the measured union at
4x and reduced it with LANCZOS to one 2048x1152 alpha texture. The generated
checker render `mask-preview.png` was inspected at native resolution: it had two
smooth symmetric lens lobes, the central top/bottom notches, and no band steps.
The DDS was packed into `MyOverhaul/stream/lex_binocular_mask.ytd`; RedM's
converter reported a successful RDR2 YTD build.

`GameplayTweaks/modules/binocular_optics.cpp` now requests that exact dictionary,
draws it only after the real optics gate, applies the existing hot-reloaded
`MaskScale` and `MaskOpacity`, and releases it on exit. Four straight rectangles
fill only the outside margins when scale is below 1.0; they do not construct a
curved edge. The 32-band loop and both mission-scaleform natives were removed.
Its heartbeat reports `loaded`, `scale`, and `opacity`, so a missing dictionary
cannot be confused with a rendered mask.

No combined build, install, game launch, shared dispatcher, main INI, manifest,
GitHub comment, label, or state was changed. Static and rendered-asset checks
passed. Actual in-game pixels remain the acceptance boundary.
