# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356302479 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182

Created: 2026-08-06T03:49:08Z; updated: 2026-09-05T06:59:10Z

Exact metadata: [source record](sources/issue-5356302479-dee5fd4b1497239ac150778048537281cb28819a346c4f1a28d56b8d548f9d1a.json).

## Idea
Apply the existing subtle `scr_event_glint` effect to nearby animals that the player can study but has not yet observed/studied for the compendium. Remove the glint immediately once the game records the study.

## Research finding
This appears feasible using Rockstar's own state rather than a mod-maintained species checklist:

- `COMPENDIUM_GET_SHORT_DESCRIPTION_FROM_PED(ped)` identifies a ped with a valid compendium animal entry.
- `COMPENDIUM_WAS_ANIMAL_OBSERVED(ped)` reports whether that animal/species is already observed.
- Rockstar's own `short_update` passes the live animal ped to the observed query before granting the study award.
- `scr_event_glint` can be attached to an entity bone, so it can follow a moving animal and anchor near its head instead of floating at the model origin.

## Proposed configuration
```ini
[CompendiumGlints]
UnstudiedAnimalsEnabled=0
GlintSize=1.0
ScanRange=60.0
```
Default off. Reuse the visual effect, but keep this independent from casing and cigarette-card glints.

## Questions and constraints to verify
- Reproduce Rockstar's exclusions: humans, invalid/dead entities, animals with tuning flag 58, and possibly horses, whose compendium path is separate.
- Verify `COMPENDIUM_WAS_ANIMAL_OBSERVED` behaves correctly in Story Mode for several studied and unstudied species; its clearest decompiled call site is in `short_update`.
- Determine whether the glint should apply to every individual of an unstudied species or only the nearest visible individual.
- Throttle nearby-ped scans and require distance/visibility so herds do not become clouds of particles.
- Stop and discard particle handles immediately on study, despawn, death if inappropriate, mission/cutscene suppression, or option disable.
- Confirm head-bone attachment across birds, fish, very small animals, and large animals; use bounds-center fallback when the bone is unavailable.

Exploratory only: the native state test makes the feature credible, but Story Mode readback and edge-category behavior require a focused runtime probe before implementation.

## issue 5356302479 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182

Created: 2026-08-06T03:49:08Z; updated: 2026-09-06T12:55:11Z

Exact metadata: [source record](sources/issue-5356302479-dc5b5145d6862661c08be2106c1af2599b16009f9e70edd515de51b5d96547f7.json).

**Status: A read-only probe is installed; the glint feature is not.** Scope includes animals, horses, plants, weapons and equipment—not animals alone.

- [ ] Set [CompendiumGlintProbe] Enabled=1 in GameplayTweaks.ini and restart. While looking at each target, press F10 once: studied/unstudied animal, known/unknown horse breed, herb before/after picking, and known/unknown weapon or equipment. Use ordinary aiming, not binoculars while #357 is unresolved.
- [ ] Attach GameplayTweaks.compendium-probe.log, identify the targets, and restore Enabled=0. The probe must not alter compendium progress.

## comment 5550130885 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182#issuecomment-5550130885

Created: 2026-08-06T03:58:36Z; updated: 2026-08-06T03:58:36Z

Exact metadata: [source record](sources/comment-5550130885-592daaae523cad43a82d9de747cefff994eaab48b45f501408be45835a718926.json).

Research result: the feature is credible using Rockstar's own compendium state. `COMPENDIUM_GET_SHORT_DESCRIPTION_FROM_PED(ped)` identifies a valid animal entry, and `COMPENDIUM_WAS_ANIMAL_OBSERVED(ped)` is called on the live ped in Story scripts before study award. The existing `scr_event_glint` can attach to an entity/bone. Remaining proof is runtime readback across studied/unstudied species and edge categories: tuning-flag exclusions, horses, birds, fish, tiny animals, death/despawn, missions/cutscenes, and head-bone fallback. Recommendation: default off, scan throttled/visible nearby peds, glint only the nearest qualifying individual per species, and discard the particle immediately when observed or invalid.

## comment 5550130902 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182#issuecomment-5550130902

Created: 2026-08-06T07:43:27Z; updated: 2026-08-06T07:43:27Z

Exact metadata: [source record](sources/comment-5550130902-b3609182ddbaade780a1d25bb3e982b0e8895aea763ca8d90d0f0dffa1cbb28d.json).

Research conclusion: the identification and state path is sound, but one correction is necessary: the public surface available here does **not** expose a confirmed `COMPENDIUM_WAS_ANIMAL_OBSERVED(ped)` getter. Story Mode uses the live ped to obtain its animal type/description, then records observation with `COMPENDIUM_ANIMAL_OBSERVED_BY_STAT_NAME(animalType, ...)` (horses use `COMPENDIUM_HORSE_OBSERVED`). `short_update.c` confirms `COMPENDIUM_GET_SHORT_DESCRIPTION_FROM_PED(livePed)` and `_GET_PED_ANIMAL_TYPE(livePed)`, but the previously claimed observed-query call was not found in the decompiled scripts or current native surface.

That means the proposed feature is not yet implementable exactly as written using the cited getter. The glint itself is feasible (`scr_event_glint` is already attached to entities by this project), and valid compendium animals can be identified, but "remove immediately once already observed" needs a readable observation-state source. The next human/runtime probe should test candidate compendium/stat readback against one known studied and one known unstudied species, plus horse/bird/fish cases. Without a proven readback, maintaining a mod-side checklist would be wrong because pre-existing save progress would be unknown.

If readback is found, use throttled visible-ped scanning, exclude humans/dead/invalid peds and horses unless separately supported, attach to head with bounds fallback, and stop the particle immediately on observed/invalid/despawn/disable. Research is complete to the available static/native evidence; no feature was implemented or game launched.

## comment 5550130912 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182#issuecomment-5550130912

Created: 2026-08-06T13:35:28Z; updated: 2026-08-06T13:35:28Z

Exact metadata: [source record](sources/comment-5550130912-672b3af4beb7945f7353d826360e99fc769cb23c76a3aeeac781f148d337a5e3.json).

This means you need a probe? Then make it and tell me what to do. 
Also I didn't mean to say animals, I thought I said everything. Plants, weapons, equipment, horses, anything that can go in the compnedium

## comment 5550130926 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/182#issuecomment-5550130926

Created: 2026-08-06T14:42:34Z; updated: 2026-08-06T14:42:34Z

Exact metadata: [source record](sources/comment-5550130926-52d2a83cfd752475113dcdbc99f95cfa76e4946349c920d2283b60e23be3d2bb.json).

Installed the read-only compendium probe in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Set `[CompendiumGlintProbe] Enabled=1`, fully restart, and press F10 once for each in this order: observed animal, unobserved animal, observed horse, unobserved horse breed, herb before and after picking another instance, weapon/equipment present in compendium, weapon/equipment absent from compendium. Attach `GameplayTweaks.compendium-probe.log`, then return Enabled=0. No compendium progress is written by the probe.
