# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356309278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/207

Created: 2026-08-06T05:59:40Z; updated: 2026-09-05T07:00:35Z

Exact metadata: [source record](sources/issue-5356309278-03ead2bc52bb2befe54ee991779b5847773ec868a267eebccfe618b1bc76a0dc.json).

Legacy TODO 134

Verify whether the increased catalog effect on improved/wide iron sights actually changes anything in game.

The shared effect may describe only the displayed benefit. Real sight behavior may live in a different file that the mod does not currently ship, so the edited effect must be identified before this is called a finished buff. A real retune may require that other file.

Related to the legacy TODO 38 and 87 work.

## Test

- [ ] Compare standard and improved/wide iron sights in game.
- [ ] Identify exactly what the edited catalog effect changes.
- [ ] Determine whether the change is only displayed or affects real sight behavior.
- [ ] Do not call the buff complete unless an actual gameplay difference is confirmed.

## issue 5356309278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/207

Created: 2026-08-06T05:59:40Z; updated: 2026-09-06T13:07:29Z

Exact metadata: [source record](sources/issue-5356309278-bcd9adae8973582929950a5058a4cb10599a3ce70104425f6644d11933959033.json).

**Status: Current data is loaded, not a confirmed stronger accuracy buff.** Improved Sights still add the vanilla 5 displayed accuracy points; the defined mechanical change is a slightly narrower view, not reduced spread.

- [ ] At a gunsmith, use the Cattleman Revolver: Customize → Components → Sights. Compare Stock Sights with Improved Sights while changing no other component; check the Accuracy bar rises.
- [ ] Aim from the same position at the same landmarks with each sight. Improved should show a narrower view. Send comparison screenshots or report no difference. Do not use Navy Revolver for this test.

## issue 5356309278 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/207

Created: 2026-08-06T05:59:40Z; updated: 2026-09-06T13:07:29Z

Exact metadata: [source record](sources/issue-5356309278-c74c23572d6cff037821b6657c9d5b65d3af125cc94fbdad74cec6bc7ac7f951.json).

**Status: Current data is loaded, not a confirmed stronger accuracy buff.** Improved Sights still add the vanilla 5 displayed accuracy points; the defined mechanical change is a slightly narrower view, not reduced spread.

- [ ] At a gunsmith, use the Cattleman Revolver: Customize → Components → Sights. Compare Stock Sights with Improved Sights while changing no other component; check the Accuracy bar rises.
- [ ] Aim from the same position at the same landmarks with each sight. Improved should show a narrower view. Send comparison screenshots or report no difference. Do not use Navy Revolver for this test.

## comment 5550137987 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/207#issuecomment-5550137987

Created: 2026-08-12T12:38:42Z; updated: 2026-08-12T12:38:42Z

Exact metadata: [source record](sources/comment-5550137987-80e27c94f57cc7a9d81c863bb2e9ac3cb0efcb558a4e98f89c7052ebc5739de7.json).

? so like what mods specifically do i buy? for what guns? how much should they be increasing the bar by? how much did they in vanilla? this isn't very helpful

## comment 5550138005 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/207#issuecomment-5550138005

Created: 2026-08-16T02:30:03Z; updated: 2026-08-16T02:30:03Z

Exact metadata: [source record](sources/comment-5550138005-efba5ce5f1624dbb153e829240327545fe1cbc53fc87cbaf195bb9e80d8d01b8.json).

Direct answer: buy **Customize > Components > Sights > Improved Sights**, then compare them with **Stock Sights** on the same gun. Use the Cattleman Revolver first because both records are in the base component file.

The current package has this pair for 22 guns:

- Revolvers: Cattleman, Double-Action, Schofield, LeMat.
- Pistols: Mauser, Semi-Automatic, Volcanic, M1899.
- Repeaters: Carbine, Lancaster, Litchfield, Evans.
- Rifles: Varmint, Bolt Action, Springfield, Carcano, Rolling Block.
- Shotguns: Repeating, Pump-Action, Double-Barreled, Sawed-Off, Semi-Auto.

The catalog also lists Navy Revolver sights, but the installed package has no Navy sight record in any `weaponcomponents.meta`. Do not use the Navy for the mechanical test.

Vanilla Improved Sights add **5 displayed accuracy points**. The current mod also adds **5**. It has not increased that value. Story's gunsmith code uses this catalog effect for the Accuracy comparison bar.

The real component values are separate. Stock Sights use `AccuracyModifier=1.0` and `CameraFovModifier=1.0`. Improved Sights use `AccuracyModifier=1.0` and `CameraFovModifier=0.95`. The defined mechanical change is a slightly narrower camera view, not tighter bullet spread.

Test one Cattleman with no other component change:

1. Compare the gunsmith Accuracy bar. Improved Sights should add 5 points.
2. Take fixed-position aiming screenshots. Improved Sights should show the narrower view.
3. If shot accuracy must be tested, fire equal 30–50 shot groups with fixed ammo, condition, familiarity, range, aim state, and camera. Measure physical group diameter on the target, not screen pixels.

The files and VFS log prove that the data loaded. No existing screenshot or shot group proves the player-visible result.
