# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356305099 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192

Created: 2026-08-06T05:48:36Z; updated: 2026-09-05T06:59:44Z

Exact metadata: [source record](sources/issue-5356305099-e8e667e8e7869b383f1f3ce5b269f7ca0a2cbbff4747142726a91d298f091dd8.json).

i got one to tag but it was so weird and finnicky for some reason. also i dont see why i should have to pick a plant before it becomes taggable. rampage editor lets me spawn in plants at will so there's clearly already a way of knowing what plants are?
## Tag visibility distance

Add independently configurable distance-based visibility for completed recon tags:

- `MaximumTagDisplayDistanceMeters`: maximum world distance, in metres, at which an existing tag may be displayed.
- `TagFadeStartPercent`: percentage of `MaximumTagDisplayDistanceMeters` at which the tag begins fading out.
- Before the fade-start distance, the tag is fully opaque.
- From the fade-start distance to the maximum distance, opacity decreases linearly.
- At and beyond the maximum distance, the tag is fully transparent and not displayed.
- Example: with a 100 m maximum and 75%, the tag is fully opaque through 75 m, fades from 75-100 m, and is invisible at 100 m or farther.
- Distances use the tagged entity's world position and must apply consistently to human, animal, and plant tags.
- Both settings must be available in the mod settings interfaces with clear names, metre/percent units, validation, and documented hot-reload or restart behavior.

## Acceptance additions

1. Confirm tags are fully visible below the configured fade-start distance.
2. Confirm a smooth distance-based fade between the configured percentage and maximum.
3. Confirm tags are completely absent at and beyond the maximum.
4. Test humans, mounted rider/horse pairs, animals, and plants at multiple maximum/fade values.

## issue 5356305099 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192

Created: 2026-08-06T05:48:36Z; updated: 2026-09-06T12:55:25Z

Exact metadata: [source record](sources/issue-5356305099-3804483c2168be2222e89889c8c58c0266cc4b0983e5c55d2cf1e019281346d4.json).

Incomplete study/tag progress should drain gradually after losing the target; completed tags must remain. The decay rate should be configurable, including zero to pause it.

**Status: Latest repair is source-only.** The recorded default is 50% per second, but that build is not installed. Deliver it before another decay-rate comparison.

## issue 5356305099 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192

Created: 2026-08-06T05:48:36Z; updated: 2026-09-06T13:55:37Z

Exact metadata: [source record](sources/issue-5356305099-32c6a1e6cda5cc9ef86605bd9c4e251533df47cb5b66248f04d544f69fec81b8.json).

Incomplete study/tag progress should drain gradually after losing the target; completed tags must remain. The decay rate should be configurable, including zero to pause it.

**Status: Latest repair is source-only.** The recorded default is 50% per second, but that build is not installed. Deliver it before another decay-rate comparison.

## comment 5550133681 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133681

Created: 2026-08-06T06:44:45Z; updated: 2026-08-06T06:44:45Z

Exact metadata: [source record](sources/comment-5550133681-0410167a98154e9c816d3399e772338512b10b70bdc12615743e9ac1b3d337e9.json).

Implementation update: the installed trace showed the plant pool scan finding zero candidates even while Rockstar's aim query returned a real entity. The code was discarding that authoritative aimed entity unless it was a ped, then scanning only the first 512 global objects. I changed plant targeting to accept a known plant directly from the aim query and expanded the fallback to independent 4096-object/2048-pickup pools; diagnostics now include the aimed model hash for any missing shipped entry. Release build passes and is queued for install when RDR2 closes. Keeping this actionable until the install lands.

## comment 5550133698 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133698

Created: 2026-08-06T08:07:08Z; updated: 2026-08-06T08:07:08Z

Exact metadata: [source record](sources/comment-5550133698-f5036669f8fce6459defe5f232d83b0e541ca8d68ee96a2fdf2d96c320455abb.json).

whoa it's a huge improvement! one small issue: the tag icons don't appear above the plant but within it

## comment 5550133709 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133709

Created: 2026-08-06T19:18:09Z; updated: 2026-08-06T19:18:09Z

Exact metadata: [source record](sources/comment-5550133709-8199269726aa4dc38e2206de098c187c3d1396e1833ae39a1a3e92925f9b75ce.json).

I can tag this creeping thyme but not this evergreen huckleberry. Weird. Why?

The icon for tagged plants is a white square. What external icon are you trying to use anyway? Also, Isn't there a white plant icon in the vanilla UI already?

## comment 5550133720 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133720

Created: 2026-08-09T08:42:12Z; updated: 2026-08-09T08:42:12Z

Exact metadata: [source record](sources/comment-5550133720-363055a8a79ae434618b19f403cae2e57c57db5f6c00eb1a9765255491054a72.json).

The installed plant scanner was the source of the latest ERROR:FFFFFFFF: a minidump proved the bulk scenario-point native overwrote selectReconPlantScenarioPoint's stack. Replaced it with a 250 ms, reticle-centered scan using _FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE for the shipped WB_ plant types; no native output buffer remains. Installed/source/manifest SHA-256: BEB2B8D83DC829772957F3187C1D1C49A3B49BC0E126807D7E03DDAC75D9F446. Leaving this in test me for plant acquisition, dwell/tag, and crash-freedom confirmation.

## comment 5550133742 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133742

Created: 2026-08-10T06:29:25Z; updated: 2026-08-10T06:29:25Z

Exact metadata: [source record](sources/comment-5550133742-4e0fa1b6405b3e85993d67687dd10be4774f7ee64423e2ed7b2d8b375784b3c7.json).

Point a gun at a dog. The "study" bar doesn't fill even as it becomes tagged. You still get the option to hold Q to study once it's tagged. Even though tagging and studying should be one and the same.
Tagging plants doesn't work at all.

## comment 5550133752 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133752

Created: 2026-08-10T07:17:04Z; updated: 2026-08-10T07:17:04Z

Exact metadata: [source record](sources/comment-5550133752-40d90b42304f4e3637b4ede20506d80690dafb3ff08523b6348fef3dd9d1253d.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test plant tagging by aiming/binocular reticle, eased dwell marker, picked-plant cleanup, and animal compendium study completion.

## comment 5550133769 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133769

Created: 2026-08-10T09:00:03Z; updated: 2026-08-10T09:00:03Z

Exact metadata: [source record](sources/comment-5550133769-2b5663fa137a5924c487682500518c51e20322d31d372614ddf4ca33c0e8dc8a.json).

When I hold Q/RB to pull out the binos, Arthur starts running to the nearest cover for a brief moment before he starts pulling out the binos instead. Not sure why this is happening when I literally told you how to do this: block the native cover command altogether. When they hold the button, send it on RELEASE if they hold it for less time than the threshold.

## comment 5550133779 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133779

Created: 2026-08-10T09:02:56Z; updated: 2026-08-10T09:02:56Z

Exact metadata: [source record](sources/comment-5550133779-cc4fcb2c64f49368baf670a6b53d0f18748a16ea31202869b684ac33028d68df.json).

Only 1 thing can be tagged at a time, which is really noticable and doesn't make sense. For example, tagging a man on his horse will tag his horse, then the man. ???

If I point my camera at someone and hold Q to pull out the binos I can clearly see his tag beginning to fade in AS I'm still pulling out the binos.

Plant tagging works again! Hooray!

## comment 5550133788 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133788

Created: 2026-08-10T09:07:53Z; updated: 2026-08-10T09:07:53Z

Exact metadata: [source record](sources/comment-5550133788-96011c7bf1fe74cd83a2604e1ea270b24bf10a98bd68a91dcbe14d48bc485656.json).

Aim tolerance screen radius does nothing btw. I set it to 1 and people still stop getting tagged the moment they move one nanometer off the center of my screen.

## comment 5550133799 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133799

Created: 2026-08-10T10:21:49Z; updated: 2026-08-10T10:21:49Z

Exact metadata: [source record](sources/comment-5550133799-83251a0c6554bb15f9e7deab9e4b3dcbf5ccc9fa65ed10b14f947fe584f2c2aa.json).

New requested behavior added: configurable maximum tag display distance in metres plus a configurable percentage of that maximum where linear fade-out begins. Tags must be fully invisible at the maximum distance. This is new implementation work, so Lexer-Lux/Lexeditor#192 is correctly back to actionable; high priority is preserved.

## comment 5550133815 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133815

Created: 2026-08-10T11:02:46Z; updated: 2026-08-10T11:02:46Z

Exact metadata: [source record](sources/comment-5550133815-78b589cda5871636bdf531dca45ca69869d3c3a3a0f34d78f424744e64b0d967.json).

Implementation update (not yet built/installed): completed recon tags now use independent hot-reloaded MaximumTagDisplayDistanceMeters and TagFadeStartPercent settings. Humans, animals, rider/horse pairs, and plants are fully opaque before the fade start, fade linearly, and are not drawn at or beyond the maximum. Existing acquisition distance, targeting, art, and minimap behavior are unchanged. Static visibility, plant, schema, and diff checks pass; Lexer-Lux/Lexeditor#192 remains actionable until runtime distance tests.

## comment 5550133837 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133837

Created: 2026-08-10T12:51:35Z; updated: 2026-08-10T12:51:35Z

Exact metadata: [source record](sources/comment-5550133837-bf125dbf793db161d73dfb1bca9ee1a0bdbe1c8ff9fc3b3e37a4b05254379ddb.json).

Only 1 thing can be tagged at a time, which is really noticable and doesn't make sense. For example, tagging a man on his horse will tag his horse, then the man. ???

## comment 5550133848 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133848

Created: 2026-08-12T12:30:51Z; updated: 2026-08-12T12:30:51Z

Exact metadata: [source record](sources/comment-5550133848-93804b6381d3896b8c47d3832935532fa8af4246663667a180ccdd789670c6c4.json).

Plant tags don't have distance text.
Plant tags don't result in map/minimap blips. There's a perfectly good map herb icon in the vanilla game files BTW. Mousing over the blip should give the plant name, just like how animal blips show their name.
When I open up Rampage trainer to spawn animals I can see each animal has their own icon. Can I see what the tag cores would look like if each animal's icon was their own icon? Is that doable?
Give me a setting to disable plant tagging.

## comment 5550133858 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133858

Created: 2026-08-12T12:34:17Z; updated: 2026-08-12T12:34:17Z

Exact metadata: [source record](sources/comment-5550133858-b1341a6af0e0960a08d1cdf01ebdf23fbc769bd26e25eef64045f5aaf6ae062b.json).

Oh and I should be able to set the distance from which you can tag something simply by aiming at it. This should NOT apply when being scoped in with a scoped weapon, which should stay with bino rules. The default max dist for tagging via weapon aim should be 50m.

## comment 5550133870 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133870

Created: 2026-08-12T12:43:03Z; updated: 2026-08-12T12:43:03Z

Exact metadata: [source record](sources/comment-5550133870-62f177756fbffe53f615d7b91c183df55064af433e4c43caebfad3d3da15b2f7.json).

Oh also blue jays and bluetick coonhounds have the same blip size? can you show me the different size animal blips and make sure the sizing logic is all ok?

## comment 5550133885 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133885

Created: 2026-08-12T12:44:35Z; updated: 2026-08-12T12:44:35Z

Exact metadata: [source record](sources/comment-5550133885-8fd0faa5524ce22c2f0a28b7dc9fc32f18f3c82c3bc9c65ef2d9023689172f4b.json).

oh and the weapon point tagging thing works if you hold RMB with no weapon out. but strangely it DOSEN'T work with a knife. out. should be the opposite....

## comment 5550133898 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133898

Created: 2026-08-12T13:07:30Z; updated: 2026-08-12T13:07:30Z

Exact metadata: [source record](sources/comment-5550133898-38da29372ffec8cb2464d84d6825b2cd54adca710030145ae96db30ad503adaf.json).

Recon now shows plant-tag distance, hot-reloads the plant-tag switch, limits ordinary weapon-aim acquisition to the new distance setting, and keeps the longer range for active scopes and binoculars. The completed-tag maximum-distance and fade settings remain independent. Test those four paths; plant species names and species-specific animal icons remain separate unresolved requirements.

## comment 5550133908 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133908

Created: 2026-08-18T18:05:18Z; updated: 2026-08-18T18:05:18Z

Exact metadata: [source record](sources/comment-5550133908-c807d3ea2b4031053cc0a4aef1980ee7c009a25428c95fc4301c06d059852e40.json).

**Horse recon tag HP — root cause found and fixed in source (not yet built).**

Both of your numbers were in the runtime log:

```
[recon] tag health ped=172802 horse=1 entity=74 maxTrue=100 maxBase=100
        core=35 attrRank=21 attrMaxRank=100 capacity=21 currentFrame=7
```

`capacity=21` is the grey "max" arc (21/99 of the ring — your "about 1/4") and `currentFrame=7` is the white arc (7/99 — your "~1/8"). `core=35` is what your HUD horse health core was showing — your "1/3".

**Root cause.** The tag was using the horse's `GET_ATTRIBUTE_BASE_RANK(horse, 16)` as the maximum length of the ring, then squeezing the health-core percentage inside that. Attribute 16 really is the horse's health stat (`player_horse.c:18650-18667`, `func_652` maps horse stat 0 to attribute 16), but its base RANK is a permanent progression level, not a fraction of the health meter. Rockstar only ever buckets it into five-rank tiers for stat labels (`player_horse.c:11824`, `func_358`) or compares it against absolute thresholds (`camp_horseshoeoverlook.c:13911`, `>= 40`). Meanwhile the core value is already a percentage — `natives.h:219-223` documents `_GET_ATTRIBUTE_CORE_VALUE` as "the ped's core value on a scale of 0 to 100". So the tag was drawing a percentage of a rank, which is why the two numbers were wrong by different factors.

The log kills the old reading outright: your horse was holding 74 HP against an engine-reported maximum of 100 while its rank was 21. `GET_ENTITY_MAX_HEALTH` is not scaled by the rank, so a 21-length ring was already contradicted by 3.5x on the same line.

**Change.** Every target now gets the whole ring, the horse included, and the horse's white arc is the health-core percentage scaled straight into it (35 -> 35/99). That is the exact number your HUD core shows, so the tag and the core now read the same. The rank is still read and still logged as `attrRank=`, but it no longer touches the drawing.

**What to check in game once this is installed:** tag your horse and compare the tag ring against the horse health core on your HUD — full circle, white arc at the same fraction as the core, at full health and after damage.

One thing I deliberately did not guess at: for the owned horse the engine reports two different health numbers at once (entity health 74, core 35). I made the tag follow the core, because the core is the meter you were comparing against. If you actually want the tag to track the entity health bar instead, say so and it is a one-line change.


## comment 5550133919 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133919

Created: 2026-08-20T09:06:30Z; updated: 2026-08-20T09:06:30Z

Exact metadata: [source record](sources/comment-5550133919-849ac4095731e21f67fef2fa8027f7bd9a96c366c4ddccfea8c3350b5db408d1.json).

Confirmed requirement: the owned-horse recon ring must show current entity health against the horse's actual maximum health. The Health Core is a separate hunger/core meter and is rejected as the source for this tag. I am moving this back to actionable and updating both the implementation and its contract so the core-based form cannot return.

## comment 5550133926 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133926

Created: 2026-08-20T09:15:15Z; updated: 2026-08-20T09:15:15Z

Exact metadata: [source record](sources/comment-5550133926-cfd234b345a63248a50635780b9d9808563389ac61f1588cdd2c6d7003d2e051.json).

The installed trace confirms the bug: the horse still had 60/100 entity health while its Health Core was 0, and the recon ring selected frame 0. The tag was reading the hunger/core meter.

The rebuilt source now uses current entity health for the horse, with the same HealthPerRing scale as every other ped. It uses the current Story horse maximum-health path, and the core remains only in the two-second diagnostic. The contract now rejects the old core branch and two related regressions.

The game is running, so I did not replace the installed ASI. After the next install, lower the horse's outer health bar and confirm the ring follows it. An empty Health Core must not empty the ring while entity health remains, and restoring only the core must not move the ring.

## comment 5550133942 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133942

Created: 2026-08-20T10:26:12Z; updated: 2026-08-20T10:26:12Z

Exact metadata: [source record](sources/comment-5550133942-b1ac44aa3cb05db88dc87e4145fc6b7baf621fa72b76f313331105b967ad33c3.json).

The installed horse ring now uses current entity health against the actual maximum. Lower the outer horse health bar and confirm the ring follows it. An empty Health Core must not empty the ring while entity health remains, and restoring only the core must not move the ring.

## comment 5550133950 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133950

Created: 2026-08-20T10:53:17Z; updated: 2026-08-20T10:53:17Z

Exact metadata: [source record](sources/comment-5550133950-bdc0ea6c770f02f4497ed1b4065a4f7e2eb7dfb9bdfc42ded8a1ee51b1499731.json).

Installed: completed tags now use direct Tag Fadeout Start and Tag Fadeout End distances. Defaults are 182 m and 184 m: full opacity through 182 m, a linear fade from 182-184 m, and no tag at or beyond 184 m. The settings also now read Study Time, Max Tagging Distance (Binos), and Max Tagging Distance (Aiming). Test the fade on a ped or animal near both endpoints; the same curve also applies to horses and plants.

## comment 5550133960 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133960

Created: 2026-08-20T19:16:45Z; updated: 2026-08-20T19:16:45Z

Exact metadata: [source record](sources/comment-5550133960-fa87640bf7d5e084bcdcd57031a56212a013b463db5b2bfca711cc9e5e2a12ad.json).

Returned test: acquisition progress disappears immediately when the target leaves the allowed reticle or target gate. Progress must persist and decay over time instead. Add a visible setting for the decay rate, apply it consistently to binocular and ordinary-aim acquisition, and preserve completed tags.

## comment 5550133968 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/192#issuecomment-5550133968

Created: 2026-08-20T19:43:01Z; updated: 2026-08-20T19:43:01Z

Exact metadata: [source record](sources/comment-5550133968-f9a529da7f310dc1026f3e8f1755731a377287db0e2ab72e5bc507a68c608396.json).

Source repair is complete but unbuilt. Incomplete Study/tag progress now drains instead of disappearing when the target leaves the valid Study or aim state. The new Study Decay Percent Per Second setting defaults to 50; 0 pauses decay. Ped and plant progress are kept separately, and completed tags do not decay. After the next install, build partial progress, leave the target, and confirm a gradual visible decrease at two different rates.
