# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356304844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/191

Created: 2026-08-06T05:38:08Z; updated: 2026-09-05T06:59:41Z

Exact metadata: [source record](sources/issue-5356304844-884d7a8ed121f8109aa274d49fc0c791cea79ec1499b5317cb1eaca7e5ac3dfa.json).

i hit the attribute overpower thing in rampage and all my cores and bars went gold...except the stamina bar. is that just some rampage weirdness or did we fuck something up here?

## issue 5356304844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/191

Created: 2026-08-06T05:38:08Z; updated: 2026-09-06T12:55:23Z

Exact metadata: [source record](sources/issue-5356304844-4b149cb75d7ebe8588e8f5a4d1b79694a9c3f04c2acbde5cf16e0184b0c8075f.json).

**Status: Cause unconfirmed; no mod fix is established.** Static evidence suggests Rampage’s command may omit the Stamina bar, but that is not a runtime diagnosis.

- [ ] On a spare save, use Rampage’s attribute-overpower command and record which outer bars turn gold. Reload, then use a normal Miracle Tonic that fortifies all three bars.
- [ ] Compare the Stamina bar in both cases. Report whether only Rampage fails or the tonic also fails, with screenshots. Do not change unrelated settings between the two checks.

## comment 5550133359 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/191#issuecomment-5550133359

Created: 2026-08-06T07:44:35Z; updated: 2026-08-06T07:44:35Z

Exact metadata: [source record](sources/comment-5550133359-1cc217ddc6366eef8716bbd63c75e31cd01b4d0136f1e18c9b63fadbf2b6afcc.json).

Static research says this is almost certainly Rampage behavior, not an overwrite from this mod.

**Evidence**
- Vanilla Story code treats the three player tanks symmetrically: attribute indices `0`, `1`, and `2` are Health, Stamina, and Dead Eye, and `short_update.c` checks `_IS_ATTRIBUTE_OVERPOWERED` for all three.
- Vanilla item-use code calls `ATTRIBUTE::ENABLE_ATTRIBUTE_OVERPOWER` for the corresponding attributes; reset paths explicitly disable `0`, `1`, and `2` (plus horse attributes `19`, `18`, `20`). So the engine supports a gold/overpowered Stamina bar.
- The player `pedhealth.meta` entry has `OverPowerEnergy 100` and `GoldCoreEnergy 100`; there is no static sign that Stamina lacks an overpower capacity.
- Repository search found no `ENABLE_ATTRIBUTE_OVERPOWER`, `DISABLE_ATTRIBUTE_OVERPOWER`, or `_IS_ATTRIBUTE_OVERPOWERED` call in GameplayTweaks/editor code. The mod's zero-Stamina swimming change reads the outer Stamina boundary while swimming; it does not manage gold/overpower state.
- Rampage's “attribute overpower” action is external to this repository, and a single missing bar is consistent with that trainer action omitting/mis-addressing Stamina or its HUD refresh.

**Human confirmation still required**
Reproduce once with Rampage's overpower command and once with a vanilla potent/miracle tonic that fortifies all three bars. If vanilla consumption makes Stamina gold while Rampage does not, this is conclusively a Rampage issue. If Stamina also fails after vanilla consumption, capture a screenshot plus a short `ATTRIBUTE::_IS_ATTRIBUTE_OVERPOWERED(player, 0/1/2)` readout before/after; that would justify investigating a runtime conflict. No code change is supported by current evidence.
