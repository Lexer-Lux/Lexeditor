# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356300100 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171

Created: 2026-08-06T03:08:31Z; updated: 2026-09-05T06:58:38Z

Exact metadata: [source record](sources/issue-5356300100-3880c448da39d785d4c9268b00310f2de4005b070725518493409d675fe774b9.json).

## Player experience
The Breath-of-the-Wild-style rule is working as intended: exhausting the outer stamina ring while swimming means death. The problem is presentation. RDR2 currently jumps straight from swimming to death, so the result feels abrupt and arbitrary instead of like the consequence of drowning.

## Constraint
Do **not** soften or otherwise change the mechanic:
- no extra stamina
- no emergency reserve
- no button-mash rescue
- no grace period in which the player can survive
- no HUD warning overlay

Zero swimming stamina must remain an inevitable death. This issue is only about making that death legible and dramatic.

## Research
Determine what Story Mode can safely use for a short drowning transition after stamina reaches zero:

1. Search vanilla/decompiled scripts and animation dictionaries for player swimming-exhaustion, struggling, submerging, choking, drowning, or water-death sequences.
2. Determine whether an animation can take control from active swimming without snapping, freezing, teleporting, or fighting the water locomotion task.
3. Investigate suitable vanilla audio, camera behavior, underwater post-processing, controller feedback, and a brief fade that can support the animation without becoming a HUD overlay.
4. Establish how to handle shallow water, deep water, currents, first person, active missions, ragdoll, and shore-edge cases.
5. Compare the safest presentation options, including a native death task if one exists versus a controlled animation followed by the unchanged death call.

## Desired result
A brief sequence—roughly a final struggle/submerge/choke beat, then death—that communicates exactly what happened. It may delay the visible death screen long enough to play the presentation, but the outcome must become irreversible the instant stamina reaches zero.

Report the viable options, concrete animation/native evidence, failure risks, and a recommended implementation before building anything.

## issue 5356300100 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171

Created: 2026-08-06T03:08:31Z; updated: 2026-09-06T12:54:51Z

Exact metadata: [source record](sources/issue-5356300100-88f335b8de0b8712017fd75f5c037a7c792023a99cf365a458675757cc388bbe.json).

At zero swimming stamina, death remains inevitable; add a readable struggle/submerge transition without a rescue window or HUD warning.

**Status: Research only.** A short engine-owned drowning-time experiment was proposed, but not built. Prepare that controlled prototype and recovery checks before asking you to drown again. The earlier zero-second and trough-animation proposals are rejected.

## comment 5550128281 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128281

Created: 2026-08-06T03:58:36Z; updated: 2026-08-06T03:58:36Z

Exact metadata: [source record](sources/comment-5550128281-4b50b7ceb3cd972d02ba65f60200f1f0ddb598d7e1b7f52ea7426be8a7b40d39.json).

Research found real drowning assets, but not yet a drop-in player swimming-exhaustion task. The archives contain drowning facial moods, `WEAPON_DROWNING`, drowning health thresholds, and mission-specific dictionaries such as `script_re@drown_murder@drowned`; mission clips are paired/staged and are poor candidates for free-swim takeover. The safest design is still: make the outcome irreversible at zero Stamina, then attempt a brief engine-owned drowning/struggle presentation before the unchanged death. A diagnostic probe must compare native damage/death behavior against a controlled clip while checking deep/shallow water, currents, first person, ragdoll, shore edges, and missions. Do not reuse a trough/paired mission animation merely because its name says drown.

## comment 5550128293 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128293

Created: 2026-08-06T05:12:09Z; updated: 2026-08-06T05:12:09Z

Exact metadata: [source record](sources/comment-5550128293-2e849be268501a30c1a7366c959a01d1f6e4e1947ff7f561f8f07109cd1831f2.json).

okay? then when stamina hits zero just lock the controls, play the animation, and make PC sink into the water. then kill. wdym drowning assets though? Multiple anims? can i see?

## comment 5550128303 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128303

Created: 2026-08-06T07:45:07Z; updated: 2026-08-06T07:45:07Z

Exact metadata: [source record](sources/comment-5550128303-2c30861124d654d1de6432b88556676524039f201048d90dd20824d04f055419.json).

Follow-up on “what drowning assets / can I see?” Static research is complete; the remaining step is visual/runtime audition.

**Concrete assets found**
The clearest named clips are all from the staged random encounter `script_re@drown_murder@drowned`:
- `quick_drown_attacker`
- `quick_drown_victim`
- `quick_drown_trough`

The encounter also uses `script_re@drown_murder@escape` / `drown_dunk_loop_victim`, paired scene resources `script@beat@town@drownMurder@drown`, and contextual dialogue `DROWNING_A_01`, `DROWNING_B_01`, `DROWNED`. These are multiple assets, but they depict one ped forcibly drowning another at a trough/water edge; they are staged, not a free-swimming exhaustion animation.

Separate data contains `WEAPON_DROWNING` and `WEAPON_DROWNING_IN_VEHICLE`, both with stat `DROWN`. Those are damage/death causes, not playable animation dictionaries. Underwater timecycle/weather assets provide the existing underwater look, not locomotion takeover.

**Recommended shape if approved later**
At zero outer Stamina: latch an irreversible terminal state immediately; disable controls; attempt a short single-ped struggle/submerge; sink or constrain Z only where depth is safe; then issue the unchanged death. Fall straight through to immediate death if the clip cannot take control, water is shallow, the ped is ragdolled, first-person cannot switch safely, or mission state forbids takeover.

**Why visual/runtime audition is mandatory**
Names do not reveal whether `quick_drown_victim` contains attacker-root motion, expects trough alignment, accepts the player skeleton, or fights swimming locomotion. These four clips can be previewed in an animation viewer/Rampage. A later read-only probe must test deep/shallow water, current, first person, ragdoll, shore edge, and active mission. Do not select an animation until that audition; forcing a paired trough clip is the main snap/freeze/teleport risk.

## comment 5550128321 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128321

Created: 2026-08-09T09:43:42Z; updated: 2026-08-09T09:43:42Z

Exact metadata: [source record](sources/comment-5550128321-a5825f6cc8d6c73f6cccae34e3e2a3201328091f53819a3943f4e90dea38101e.json).

i don't understand, you want to play an animation of someone being drowned in a trough to represent our pc drowning in a body of water???

## comment 5550128329 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128329

Created: 2026-08-09T09:59:16Z; updated: 2026-08-09T09:59:16Z

Exact metadata: [source record](sources/comment-5550128329-b79bc9bce7ce89c7a31096898900d52271bad5593db464cc99dbcb1f27b451b5.json).

Second-pass correction: **No—we should not use an animation of someone being murdered in a trough to represent the player drowning in open water. That earlier direction was wrong and is retracted.**

A genuine standalone open-water drowning locomotion set was missed:

- `mech_swim@streamed_drowning` — `drown`, `idle`, swim start/stop, turns, walk/turn clips (`ingameanims_list.lua:314131-314145`)
- `mech_swim@streamed_tired` — tired swim locomotion (`:329013-329025`)
- `mech_swim@streamed_panic` — panic run/sprint swim locomotion (`:120040-120047`)
- `ai_damage@ko@base` — single-ped `drown`/`drown_cuffed` death reactions (`:115010-115021`)

`mech_swim@streamed_drowning` is independently present in the archive/string inventories (`ArchiveItems.txt:2813108`, `DataLines.txt:2985285`). Its full set of matching swim transitions establishes that it belongs to the engine swim-locomotion family, not a staged paired scene.

The following are explicitly disqualified:

- `script_re@drown_murder@drowned` and `@escape`: synchronized attacker/victim/trough tracks.
- `mini_games@story@saloon1@drown@arthur/patron`: coordinated Arthur/patron trough move networks.
- Guarma `drown_rapids_idle_cam`: camera-only.
- horseback drowning sets: mounted-rider context.
- animal drowning sets: incompatible skeleton/context.

`MoodDrowning` is also real and resolves through the player facial groups, but it is only a facial mood. Drowning cough/gasp strings exist, but no authoritative Story playback call site was found, so they are not yet safe audio calls.

### Why the current death is abrupt

`GameplayTweaks/script.cpp:2342-2349` is stateless. On the first frame where the player is actively swimming and outer Stamina is `<= 0.01`, it directly calls `SET_ENTITY_HEALTH(ped, 0)`. There is no drowning task, terminal presentation state, sink, audio, camera, fade, or explicit `WEAPON_DROWNING` cause. That direct health-zero call bypasses the engine swim/drowning state machine.

The predicate excludes ordinary shallow-water wading only because `IS_PED_SWIMMING` must be true. It does not classify near-shore swimming, depth, current, ragdoll, first person, or missions. Missions are not excluded from the current death rule.

### Safest engine-owned prototype, if implementation is approved

The strongest first candidate is **not** direct `TASK_PLAY_ANIM`. These `mech_swim` sets appear engine-owned locomotion dictionaries, and forcing one as a generic animation could fight buoyancy, currents, and shore transitions.

Rockstar exposes `SET_PED_MAX_TIME_IN_WATER` (`0x43C851690662113D`). `train_robbery1.c:54371-54382` uses it with ped config flag 265; the authoritative config table names 265 `PCF_DrownsInWater`. `short_update.c:3325-3342` enables that flag for the normal player, and respawn restores the relevant drowning flags. Flag 266 is `PCF_DiesInstantlyWhenSwimming` and should not be used because it likely preserves the abrupt result.

Recommended dev-only A/B:

1. At the exact existing zero-Stamina edge, raise an irreversible terminal latch immediately. Surfacing, reaching shore, or regaining control must never cancel it.
2. Keep `PCF_DrownsInWater` under engine ownership and call `SET_PED_MAX_TIME_IN_WATER(ped, 0.0f)` once.
3. Observe whether the engine naturally selects `mech_swim@streamed_drowning/drown` or `ai_damage@ko@base/drown`, produces a visible struggle/submerge, and records cause `WEAPON_DROWNING` (`0xFF58C4FB`).
4. If the engine has not entered dead/dying within a short bounded presentation window (candidate: about 2.5 seconds), execute the unchanged health-zero fallback. The latch means this is presentation time, not survivable grace.
5. Only if the engine route does not select the real drowning locomotion should a second probe directly play `mech_swim@streamed_drowning/drown`.

Do not initially add a scripted camera, forced coordinates/heading, manual Z sinking, post-FX, fade, guessed drowning voice, or persistent controller shake. Let the engine own swimming/current, underwater presentation, `DYING_SCENE`, death camera, and respawn. For missions or any state where Rockstar has disabled its drowning flag, use the existing immediate-death fallback instead of taking over mission state.

Acceptance must prove visible struggle/submerge before death; inevitable death even at the shore edge; no snap/freeze/teleport; real drowning cause; clean normal respawn; and no residue. Test deep still water, current, shallow non-swimming water (must not arm), shore edge, first person, ragdoll-at-trigger, and an active mission.

This is exploratory research only. No code, build, install, label, or issue-state change was performed, and no animation has been claimed visually correct without the required runtime audition.

## comment 5550128337 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/171#issuecomment-5550128337

Created: 2026-08-11T07:13:37Z; updated: 2026-08-11T07:13:37Z

Exact metadata: [source record](sources/comment-5550128337-8e061613eb807bce0008897a27f639772cc39c5177dd767e3fd7988a7fc9997a.json).

Correction: do not use `SET_PED_MAX_TIME_IN_WATER(ped, 0.0)` for the drowning presentation. Zero seconds is the wrong first test and can preserve the abrupt death.

Story Mode gives three useful comparisons: a lost drunk gets `PCF_DrownsInWater` with 3 seconds; doomed train robbers get the same flag with 0 seconds; and a character protected from drowning gets seven hours. This shows that the value controls drowning time. It does not prove whether changing it after swimming starts resets the timer, and the checked natives have no matching getter.

The safer dev-only test is to latch irreversible death at zero outer Stamina, leave the existing drowning flag unchanged, set water time to 3 seconds once, and observe animation, submerged state, health, death state, and cause of death. If the engine does not complete the death in a short fixed window, use the existing health-zero fallback. After respawn, verify that the new player ped has normal water behavior.

The first test must not force Z motion, a generic animation, a camera, or post-effects. We must first see whether the engine selects its real drowning locomotion.
