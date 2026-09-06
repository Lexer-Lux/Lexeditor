# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356284862 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105

Created: 2026-08-06T01:29:26Z; updated: 2026-09-05T06:55:00Z

Exact metadata: [source record](sources/issue-5356284862-00afb133be710dc2659cae47204f95c9ed608a0aadd2962113dbd1f988fa815d.json).

## Current requested behavior

Keep a lantern attached to the player's belt. The lantern must not hover inside the torso and must not remain held in the player's hand.

The lantern stays present but unlit when it is off. Selecting the lantern through Rockstar's radial controls the belt lantern's on/off state. The radial is the player control; time of day must not force the light on.

Acceptance:

- The lantern is attached at the correct right-belt/hip bone, not the entity center.
- Selecting a lantern in the radial toggles the belt light and returns the player from the hand-held lantern state.
- Turning the light off leaves the unlit lantern on the belt.
- The attachment has bounded movement and does not push, jitter, or damage the player.
- Mission-supplied lantern behavior is not intercepted.
- Failure to resolve either attachment bone is logged and creates no prop.

## Original request

Lantern object should no longer appear in radial outside of missions. Instead, it should be physics-rigged and attached to the player's belt, automatically activating/deactivating when it's night and/or dark.
Currently it just hovers within my chest lol.

## Later player decisions

The lantern must remain present when unlit. The radial must be restored so the player can control the light manually. Runtime testing of the vanilla-only fallback failed because it left the lantern in the player's hand.

## issue 5356284862 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105

Created: 2026-08-06T01:29:26Z; updated: 2026-09-06T12:46:10Z

Exact metadata: [source record](sources/issue-5356284862-114fe89bf743b3de0911b35242a8f13eaa1e218192c1b076bbbdf178859d0d19.json).

Keep the physical lantern on the belt when unlit. The radial controls its light; crouching uses the agreed dimmed behavior and standing restores the prior state. Mission lanterns remain unaffected.

**Status: Latest repair is not built or installed.** Crouched radial availability still needs proper feedback, and brightness/range remain broken in #290. No final retest is ready.

## comment 5550110097 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110097

Created: 2026-08-06T08:09:02Z; updated: 2026-08-06T08:09:02Z

Exact metadata: [source record](sources/comment-5550110097-e6233fc0337ac0b79456d86d9d5c65884dd596809e643aa4c853e1d8ac6b1878.json).

The combined release build now includes the repaired actual carried-lantern model, right-hip attachment, damped sway, and night/interior activation. It remains queued until RDR2 exits.

Queued ASI SHA-256: `5E08E021F25A1B0A597B350451514544086EE8898949E98608D0C8BAF05855CC`

## comment 5550110119 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110119

Created: 2026-08-06T08:16:10Z; updated: 2026-08-06T08:16:10Z

Exact metadata: [source record](sources/comment-5550110119-9e51689233ef65eadc7a4a52b61096c1536fea90afafe764e86cce78c8f47963.json).

Superseding combined build queued; includes the belt-lantern repair. It will install when RDR2 exits.

Queued ASI SHA-256: `9124F920A8A97381327D8FF1D2E01A0A3220A793EA9BE475BAF5D7198E9B225B`

## comment 5550110139 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110139

Created: 2026-08-06T11:45:53Z; updated: 2026-08-06T11:45:53Z

Exact metadata: [source record](sources/comment-5550110139-9e437dff754e9d9e2456d90905d6908aaaa8c4cf76e856cd99ca8e83be7335a1.json).

how do i get the belt lantern? where is it?

## comment 5550110158 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110158

Created: 2026-08-06T11:51:56Z; updated: 2026-08-06T11:51:56Z

Exact metadata: [source record](sources/comment-5550110158-00677b037403af652acabb05be285ddf9c54f9f4946d10aab47d2d25e869a5f2.json).

It is not an inventory/radial item. With [BeltLantern] Enabled=1, it is supposed to appear automatically on Arthur/John's right hip from OnHour through OffHour, and inside a valid interior; it removes itself in daylight outdoors, missions, swimming, ragdoll, or death. I am leaving this actionable because your report means that automatic visibility has not yet been demonstrated in-game.

## comment 5550110183 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110183

Created: 2026-08-06T12:23:53Z; updated: 2026-08-06T12:23:53Z

Exact metadata: [source record](sources/comment-5550110183-3337a121d0264589f4243f9a7e27fbf39eb7f6fe431cdac735e5228393600441.json).

it can't just turn off during the day? it has to fully disappear when not on?
anyways. it's still hovering inside me, just a bit higher up and to the right. instead of my belt.
and it's just not possible to physics rig it and give it collision so it doesn't go into my body?

## comment 5550110202 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110202

Created: 2026-08-06T13:26:33Z; updated: 2026-08-06T13:26:33Z

Exact metadata: [source record](sources/comment-5550110202-d19bacba5dc40679b665c3c9ebc4ab0ceacd739089dbca6e133d16a5fbeb7246.json).

Research result:

The lantern remains inside Arthur because the current build requests bone ID `11816`, which does not exist in Arthur's extracted skeleton. Arthur's actual `PH_R_Hip` is `60844`, with separate right-belt collision points. The code also explicitly disables lantern collision, so the present “physics” is only scripted rotation on a rigid attachment.

Rockstar exposes and uses physical prop-to-ped attachment, so a genuinely swinging, world-colliding belt lantern is feasible to prototype on the correct hip bone. Collision with Arthur himself should remain suppressed to avoid pushing/jittering him; perfect collision against every body/coat shape would require a custom rigged metaped accessory. Daylight deletion is only our policy: the prop can stay attached and simply stop emitting light.

Recommended future implementation: persistent unlit daytime lantern on `PH_R_Hip`/`CP_R_Belt`, physical joint, world collision enabled, player-pair collision suppressed, bounded detach failsafe, and in-game offset/joint tuning. Research does not claim final placement or collision is proven until that prototype is visually tested.

## comment 5550110214 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110214

Created: 2026-08-09T07:37:02Z; updated: 2026-08-09T07:37:02Z

Exact metadata: [source record](sources/comment-5550110214-a7b8cb53ca212f9d9fa2fdea5990be593051901f3323b5ab415730989ba88c0b.json).

Second-pass research result:

The prior diagnosis is confirmed, and the source was never repaired. `belt_lantern.cpp:86-89` still requests bone ID `11816`, absent from Arthur’s extracted skeleton. The primary skeleton file identifies `PH_R_Hip` as ID `60844`/index 72, `CP_R_Belt` as `44381`/index 590, and `skel_pelvis` as `56200`/index 1. SDK `natives.h:1424` documents that a bad bone index attaches at entity center, matching the chest hover.

The current code also disables collision and reapplies rigid `ATTACH_ENTITY_TO_ENTITY` every frame, so it is not physical rigging. Rockstar Story scripts prove physical prop-to-ped and named bone-to-bone attachment. Resolved SDK symbols are `ATTACH_ENTITY_TO_ENTITY_PHYSICALLY` (`0xB629A43CA1643481`), `GET_ENTITY_BONE_INDEX_BY_NAME` (`0xBACA8FE9C76C124E`), and `SET_ENTITY_NO_COLLISION_ENTITY` (`0xE037BF068223C38D`). Vanilla weapon data uses `ID_PH_R_HIP`; our lantern carriable identifies `ID_GUN_GRIPR`.

Recommended future prototype: resolve lantern `Gun_GripR` and player `PH_R_Hip` by name, abort/log on `-1`, create the physical joint once per spawn/owner transition, enable world collision, and symmetrically suppress only lantern↔player collision. Keep the lantern visibly attached but unlit during daylight. Darkness/interior state should be rate-limited; only light drawing belongs per frame.

Unknown until visual testing: John’s bone coverage, safe values for the 22-argument physical joint, coat interference, mount/ragdoll stability, displacement failsafe, and emissive behavior. No implementation or label change was made.

## comment 5550110235 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110235

Created: 2026-08-10T06:07:04Z; updated: 2026-08-10T06:07:04Z

Exact metadata: [source record](sources/comment-5550110235-e294392424f366c088033b385c82210ca02abbd9d76124a8ac7d75d435effeb9.json).

Lexer authorized implementation. I restored the exact vanilla WEAPON_MELEE_DAVY_LANTERN and WEAPON_MELEE_LANTERN_ELECTRIC quick-select records to SUB_GROUP_MELEE_LIGHT at sort orders 90 and 100. GameplayTweaks.ini now defaults [BeltLantern] Enabled=0, so the broken automatic prop no longer forces a light and Rockstar's radial/equip/holster path owns lantern control. XML parses, and both restored records match the extracted vanilla quickselectitems file exactly. This is source/data only while the main integration task is active. Lexer-Lux/Lexeditor#105 remains actionable until integration builds, installs, hash-verifies, and checks the radial in game.

## comment 5550110252 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110252

Created: 2026-08-10T07:16:33Z; updated: 2026-08-10T07:16:33Z

Exact metadata: [source record](sources/comment-5550110252-c32857f38700d906968a47ee25c49324679bbf8ec7d23f0fae736603aae8b280.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test the vanilla Davy/electric lantern radial entries at sort 90/100; the custom automatic belt lantern remains disabled.

## comment 5550110275 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110275

Created: 2026-08-10T07:48:05Z; updated: 2026-08-10T07:48:05Z

Exact metadata: [source record](sources/comment-5550110275-884b7316dae62d8f057db5a1b004a02b4be654a965ff0e139b0380b66aa3f9d6.json).

Runtime failure: restoring the vanilla radial only produced Rockstar's hand-held lantern. That does not satisfy the on-belt lantern request. Lexer-Lux/Lexeditor#105 is reopened as actionable. Corrected target: the lantern remains on the belt; selecting the lantern through the radial controls the belt light instead of leaving the lantern in Arthur's hand.

## comment 5550110299 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110299

Created: 2026-08-10T08:05:33Z; updated: 2026-08-10T08:05:33Z

Exact metadata: [source record](sources/comment-5550110299-54e58f6262acafe48c6a9b12fe26e0f4d9beede4d52783bb493d2e3fd403145d.json).

Source repair is ready for integration. It replaces the invalid numeric bone and automatic time/interior gate with named PH_R_Hip/Gun_GripR physical attachment, a persistent unlit prop, and one radial selection per light toggle. It waits for Rockstar's weapon-swap task to become idle before returning Arthur from the hand-held lantern state. World collision remains enabled; only player/prop collision is suppressed. Static Lexer-Lux/Lexeditor#105 checks and exact vanilla Davy/electric radial record comparison pass. This is not installed or accepted in-game yet, so Lexer-Lux/Lexeditor#105 remains actionable until the combined build is installed and hash-verified.

## comment 5550110322 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110322

Created: 2026-08-10T09:30:13Z; updated: 2026-08-10T09:30:13Z

Exact metadata: [source record](sources/comment-5550110322-babbb0689c38d4bc9f7e4554c3e569a9cee7a18cf9dbcae7682747ebfb81fe3b.json).

Well I restarted the game and it's still totally broken.

## comment 5550110338 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110338

Created: 2026-08-10T10:40:51Z; updated: 2026-08-10T10:40:51Z

Exact metadata: [source record](sources/comment-5550110338-45b76d188abd96cf01db8ce5f642e00693ef0b434322d6166974c201a80b6235.json).

<img width="556" height="961" alt="Image" src="https://github.com/user-attachments/assets/ac447b9d-042a-43fd-a463-44f446f3e7af" />
I THINK it seems to be a lot better except uh...it's been rotated 90 degrees the wrong way lol. It's pointing backwards, not at the ground

## comment 5550110349 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110349

Created: 2026-08-10T10:57:15Z; updated: 2026-08-10T10:57:15Z

Exact metadata: [source record](sources/comment-5550110349-3f2233f952d6550e4ecab7794396661e1096307e006d1c261bddc50bfbd425a1.json).

Returned-test root cause found and repaired in source: the installed log proves the physical belt-lantern constraint stayed attached; the remaining screenshot defect was pose. Zero local rotation pointed its long axis rearward. The attachment now uses +90 degrees local X so the body hangs toward local -Z/down, without changing bones, offsets, collision, radial toggle, or stow behavior. Remains actionable until rebuilt/installed and tested through movement/mounting.

## comment 5550110368 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110368

Created: 2026-08-10T12:05:22Z; updated: 2026-08-10T12:05:22Z

Exact metadata: [source record](sources/comment-5550110368-3ea4c080ffa694d6f9ad1c5e5cb618c961cedc57dcf02bac8d0046b204675d29.json).

i can't even see it anymore. i think you rotated it along the wrong axis or something and now it's inside his body?
also: is there any way to make the PC's body "transparent" to the light from the lantern alone? because otherwise it will only light up one tiny area, with the rest of the light being blocked by his body....

## comment 5550110382 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110382

Created: 2026-08-10T15:25:17Z; updated: 2026-08-10T15:25:17Z

Exact metadata: [source record](sources/comment-5550110382-5bb544b2968ca0b55e77b2039ef1902fdc81ed11ae35eb96fb8081922f2eeb62.json).

Now it's facing the right direction but it doesn't really seem to be actually physics-rigged because it's constantly clipping through my gun holster and knife since it's attached right at the same place as them, as well as clipping through my leg every time I walk.
Is there just no solution for this?

## comment 5550110399 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110399

Created: 2026-08-10T17:15:05Z; updated: 2026-08-10T17:15:05Z

Exact metadata: [source record](sources/comment-5550110399-f2df23c8f36753f107ae92ab2b03f50f82a503b75e8b048432cbb82ba5599b3a.json).

The latest clipping report is not being answered with another guessed offset or rotation. Rockstar's Story lantern data routes WEAPON_ATTACH_POINT_LANTERN to the player skeleton's PH_Belt_Thrower bone. The source candidate now changes only the owner anchor from CP_R_Belt to that exact vanilla lantern-holster anchor; pose calibration, physical constraint, collision policy, radial toggle, and stow path are unchanged. Lexer-Lux/Lexeditor#105 remains actionable until this is built/installed and visibly clears the gun holster, knife, leg, and clothing during movement.

## comment 5550110421 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110421

Created: 2026-08-10T17:20:36Z; updated: 2026-08-10T17:20:36Z

Exact metadata: [source record](sources/comment-5550110421-87b8967bce3473c6293d78da38f722d50ae4cc87f11cf0e0c8d5e8ed4291dd17.json).

The vanilla lantern-holster anchor candidate is now installed. It uses PH_Belt_Thrower, the exact player bone to which Rockstar maps WEAPON_ATTACH_POINT_LANTERN; no guessed angle or offset was added. Test the visible lantern while walking/running, with gun holster and knife equipped, mounted, and across clothing. It must hang freely without entering the leg, holster, knife, or torso, and radial on/off plus hand-held stow must still work.

## comment 5550110444 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110444

Created: 2026-08-10T18:19:35Z; updated: 2026-08-10T18:19:35Z

Exact metadata: [source record](sources/comment-5550110444-7ad603a6cf5f1b8410ce7d8cbb1eb917efed0c0dd6feae45bf34d202677b9620.json).

Okay but now it's still clipping through his leg. Can you actually physics rig it or no?

## comment 5550110453 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110453

Created: 2026-08-10T23:40:20Z; updated: 2026-08-10T23:40:20Z

Exact metadata: [source record](sources/comment-5550110453-6e589ddcdf3598ffa5c9e0b838955bd310001e1484274c37e80588317eb6fb6b.json).

Direct answer: yes, the current lantern is already physics-rigged. It uses one `ATTACH_ENTITY_TO_ENTITY_PHYSICALLY` constraint from Rockstar's `PH_Belt_Thrower` player bone to the lantern's `Gun_GripR`; the installed test proved that constraint remained attached.

That does not give the prop collision against Arthur's animated leg, coat, knife, or holster. Player-pair collision is deliberately disabled because enabling collision between a ped and a prop physically constrained to that same ped makes the constraint push/jitter and can damage or launch the player. ScriptHook exposes no safe per-accessory collision or cloth-volume exclusion.

So the remaining requirement cannot be fixed by another script offset, angle, or bone. It needs a custom metaped lantern accessory rigged/weighted to the player skeleton and tested across outfit variants. I am moving this from `actionable` to `needs a human` for that asset/rigging work; it is not `test me`, and I am not claiming the clipping is fixed.

## comment 5550110474 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110474

Created: 2026-08-11T06:01:43Z; updated: 2026-08-11T06:01:43Z

Exact metadata: [source record](sources/comment-5550110474-3ff2adefadf66acdc158b8d0f9da4c65262aed75aec1037a27207c7527bdaab3.json).


Okay. How do I get this? Metaped? What exactly do we need? How do we get it? How do we make it work across outfit variants? Are there any reference mods we could use?

## comment 5550110492 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110492

Created: 2026-08-11T07:13:30Z; updated: 2026-08-11T07:13:30Z

Exact metadata: [source record](sources/comment-5550110492-adda6ceb8770a03d129ceb8f50519f5c617d6aaf9518c887965cadcc47e15a73.json).

Direct answer: I was too definite when I said that a custom MetaPed lantern was the solution. A normal weighted MetaPed mesh follows the player skeleton, but it does not swing. A swinging wearable needs a character-cloth asset: a YDD model with player bones and weights, plus YLD cloth-simulation data.

We need separate Arthur and John assets; a fixed belt mount; simulated lower lantern parts; YDD, YTD, and YLD files; MetaPed component records; and compatibility variants for shirts, vests, and each coat state. Rockstar uses separate clothing-state variants even for satchel straps. Its cloth data has thigh collision capsules, so a cloth lantern can react to the legs in principle. It still does not prove collision against the gun holster or knife; those can need separate clearances.

The available [Sollumz RDR fork](https://github.com/Sollumz/Sollumz_RDR) is experimental. Its documented format list includes YDD but not YLD. We therefore need an experienced RDR character-asset author or a proven YLD export workflow.

Useful references:

- [Stash That Lantern](https://www.nexusmods.com/reddeadredemption2/mods/333) shows the desired satchel behavior, but it is a script attachment and its assets require the author's permission.
- [Catalogue Improvements](https://www.nexusmods.com/reddeadredemption2/mods/5440) is a useful reference for player equipment, cloth behavior, and outfit-specific clipping fixes.

This is the correct asset scope, not a promise that an untested pipeline will remove all clipping.

## comment 5550110514 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110514

Created: 2026-08-12T12:06:54Z; updated: 2026-08-12T12:06:54Z

Exact metadata: [source record](sources/comment-5550110514-12ec37b03a1cb7eb9b9b98e4d9eb3d5908fa022b218ae936e83860c541299dc7.json).

Correction after checking the current Sollumz RDR fork itself: it contains character-cloth and YLD code, but its RDR path does not use that code.

The YDD importer loads a companion YLD only in GTA mode. The exporter can create YLD data, but it binds that cloth data to the drawable only in GTA mode. Thus the blocker is not simply that YLD is absent from the documented format list: the present RDR import and export routes do not enable it.

A working swinging MetaPed lantern still needs either a fork that enables and validates this path for RDR, or an asset author with a proven RDR YLD workflow. No existing local tool proves that we can produce a working RDR character-cloth lantern.

## comment 5550110537 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110537

Created: 2026-08-20T07:23:38Z; updated: 2026-08-20T07:23:38Z

Exact metadata: [source record](sources/comment-5550110537-f9861b5e3069044b981a9d2a4313406cb2335c84f0e1359db49776f6397fa236.json).

Weird issue. If I change the offset in the settings the lantern moves for a split second, then goes back into its place on the belt.

## comment 5550110554 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110554

Created: 2026-08-20T08:28:51Z; updated: 2026-08-20T08:28:51Z

Exact metadata: [source record](sources/comment-5550110554-3632dd14db7539e155c3c998294a9e189099bc2872fd9350d396d3d7b9df712b.json).

Found the snap-back cause. The 250 ms settle check kept the best result from the previous target, so it restored the old offset after every live setting change. A changed offset now starts with a clean settle baseline before the lantern is attached again.

I also matched the physical-joint call to the current Rockstar ped-owner form. This remains a rigid swinging prop joint, not a cloth/YLD wearable, so it does not prove universal leg or coat collision.

After the next install: set OffsetX to +0.500, wait several seconds, then set it to -0.500. Each position must move and stay instead of snapping back.

## comment 5550110570 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110570

Created: 2026-08-20T09:32:19Z; updated: 2026-08-20T09:32:19Z

Exact metadata: [source record](sources/comment-5550110570-20b6793b64778b7e05d333dc7ea27a3e47ca5efb1041286e371cedf6d310247c.json).

Confirmed in Story: the belt lantern now behaves as a physically attached prop instead of hovering statically in the torso. This passes the physics-attachment part of the issue. The newer offset-persistence repair is not installed yet, and the separate size setting still has no visible effect, so this issue is not complete.

## comment 5550110590 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110590

Created: 2026-08-20T10:26:09Z; updated: 2026-08-20T10:26:09Z

Exact metadata: [source record](sources/comment-5550110590-9372a4ae89e9a27b679dcaf1f098469a76d78580489fae032d2b6ab1ab4510cd.json).

The offset-solver repair is now installed. The physical joint you accepted is unchanged. Set OffsetX to +0.500, wait several seconds, then set it to -0.500. Each position must move and stay instead of snapping back. Dynamic size control was removed because the current setter changed stored state but did not change measured geometry; Lexer-Lux/Lexeditor#260 records that unsupported boundary.

## comment 5550110620 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110620

Created: 2026-08-20T14:05:15Z; updated: 2026-08-20T14:05:15Z

Exact metadata: [source record](sources/comment-5550110620-cb0c5dcb0a91540f8aa3e2f2071dc74bafe9ca92a111fc49aa545cb890a70444.json).

The attachment dropdown is now in source. Belt Lantern > Attachment Point offers nine resolved PH_* equipment anchors: vanilla lantern point, front/rear/melee belt points, left/right hip, and left/right holster. PH_Belt_Thrower remains the safe default. Changing the choice hot-reloads at 4 Hz, removes the old prop, and rebuilds the physical joint on the selected named bone; an invalid manual value falls back instead of attaching at the entity center. The Lexer-Lux/Lexeditor#105 and settings contracts pass, including four attachment mutations. This has not been built or installed.

## comment 5550110643 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110643

Created: 2026-08-20T19:16:46Z; updated: 2026-08-20T19:16:46Z

Exact metadata: [source record](sources/comment-5550110643-e6abc5963dacb233e579f95e80ccc75c7ed96b7f89d864b13351ea3c0f9bf599.json).

Returned design correction: remove automatic time-of-day lantern switching. The lantern item controls the saved on/off state. Crouching temporarily forces dim light, standing restores the prior on/off and brightness state, and the lantern item must be unavailable while crouched rather than changing that saved state.

## comment 5550110657 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/105#issuecomment-5550110657

Created: 2026-08-20T19:42:57Z; updated: 2026-08-20T19:42:57Z

Exact metadata: [source record](sources/comment-5550110657-75b390eaa42357cd4b0d2b67c3d55b26aa03b35ccba9bc0a069af82297a9d9fb.json).

Source repair is complete but unbuilt. The radial lantern is now the only saved on/off switch while standing. Crouching temporarily forces the player light on at no more than 0.8 brightness; standing restores the prior saved state and configured brightness. Selecting the lantern while crouched is rejected and cannot change the saved state. A true greyed radial entry remains blocked because the game provider handle and item context are unresolved; I did not add a guessed UI write. After the next install, test on/off while standing, crouch dimming, a rejected crouched selection, and restoration on standing.
