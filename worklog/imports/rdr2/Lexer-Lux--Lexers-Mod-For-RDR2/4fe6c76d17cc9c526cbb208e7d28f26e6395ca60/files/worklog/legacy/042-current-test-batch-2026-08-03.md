# Worklog: 042 Current Test Batch 2026 08 03

## Current test batch — 2026-08-03

- #1: `GameplayTweaks.reserve.log` proves the horse core fell with the outer bar:
  at 7.93/140 outer Stamina the core was 20; at 5.58 it was 14; at 3.32 it
  was 8; at 0.77 it was 2. The exhaustion latch waits for 0.5% of the bar and
  updates `protectedHorseStaminaCore` to the already-lowered live core until
  then. The gate therefore protects only the last reserve ticks, not the core.
- #7: both project and installed INIs use `Enabled=1`, `Multiplier=0.1`. The
  code calls native `0xC0258742B034DFAF` every frame, but the user saw no visible
  density difference. Presence of the call is not proof that it governs Story
  ambient-wildlife streaming.
- #11: the old implementation only applies simultaneous global recharge and
  depletion multipliers. The reusable `StaminaDrain` added for climbing solves
  a different but relevant problem: vanilla core-to-ring recovery can exceed a
  scripted drain, so it owns a monotonically decreasing target and subtracts
  only the amount required to reach that target. Generalize this into one
  signed per-mode controller and add a horse/ped path; never run drain and
  recovery ownership simultaneously.
- #42: the regular wheel carrier now renders. The code calls
  `INVENTORY_SET_CLOTHING_ACTIVE(..., true)` every 500 ms, directly explaining
  the permanent check mark and “remove” prompt. `carryActive` excludes missions
  only, so camp and task/interaction locks are not represented. The latest log
  observed Metal and Psycho but never Black Hood; the current wardrobe observer
  is not authoritative for every mask selection.
- #55: the seventh Breakdown filter and its LEXEDITOR assignment UI are retired.
  Runtime injection code, INI sections, localization, and editor/server endpoints
  are removed. `breakdown_recipes.csv` remains as design evidence for the future
  custom crafting system.
- #59: `GameplayTweaks.campsites.log` contains only
  `started player_camp thread=174 site=0`. That proves script launch, not camp
  initialization or visible materialization. A thread ID plus marker/prompt is
  insufficient success evidence.
- #93: user confirmed the complete partial-payment transaction in-game.
- #103: both latest tests started with 5 Empty Bottles and ended with 5;
  `_INVENTORY_ADD_ITEM_WITH_GUID` returned success but `realDelta=0` because the
  satchel cap was already full. The current final-swig event fires about two
  seconds after interaction start and is visibly too early. The stock item is
  `CI_CATEGORY_PROVISION` but its vanilla-style tags/flags do not place it in a
  visible satchel list; visible inventory placement is a separate unresolved
  requirement.
- #112: `VisibleProjectile` is explicitly a synthetic camera/player-chest ray.
  It uses `_DRAW_MARKER` plus `DRAW_LIGHT_WITH_RANGE`; it neither reads nor
  follows the real projectile entity/path. This exactly explains the vehicle-
  corona appearance and divergence from Rockstar's actual trail.
- #113: the tested installed INI had `[ReconTagging] Enabled=0`; the feature was
  fully disabled, so no tagging acceptance can be inferred. Project and installed
  INIs are now corrected to `Enabled=1` and hash-identical for the next test.
- #144: user reports the loaded-ammunition icons disappeared. Current policy is
  to leave loaded AMMO textures vanilla and reserve `LEX_INVENTORY_ITEMS` custom
  cartridge/casing art for the six spent-casing ingredient records only.
- #151: user confirmed the floating-binocular-model glitch fixed.
- #166: screenshot and user report show added icons as black squares. Dictionary
  load logs only prove a TXD was present/streamed; they do not prove sprite-name
  resolution or correct rendering.
- #167: user confirmed ordinary O'Driscoll red dots still appear outside a
  mission. Recon entity blips do not suppress Rockstar's independent dots.
- #169: the climbing trace retains `g_climbCache` normals/points for minutes
  after detachment (`cacheAge` exceeded 600 seconds). Grounded manual-candidate
  logic can therefore reuse a stale prior wall contact after unrelated movement,
  explaining the shrub-to-barn teleport. The trace also shows movement changing
  the owned anchor before the new movement clip is established, matching the
  reported slide-before-animation. UFCO's published design explicitly supports
  normal-input movement in every direction and corner wrapping, so lateral
  traversal is not an engine impossibility. Its decompiled implementation moves
  the whole ped along continuously probed surface coordinates, adjusts heading,
  and plays fixed `mech_ladders@base` clips. It has no per-limb IK/contact path;
  the author likewise documents that the animation does not adapt to the wall
  and that clipping is generally unresolved. Restore the surface-tangent lateral
  solver, but design our own contact correction for hands and feet.

---

Sections in order: ACTIONABLE -> WAITING -> TESTING -> COMPLETE -> DROPPED.
Every entry states the feature, the implementation work, and its current
feasibility. An item belongs in exactly one section.
Anything ending with an X = manually flagged as too hard for, or experienced severe trouble with implementing using, GPT. Fable is to implement (or fix the implementation of) them.
Ending in an ! = needs computer control to do.

<Actionable>

	<Processing>
	CLass C: Look into the RDO train logic. Not only do they have trains on their map, they have little arrows on them that show which way they're moving. Awesome!
	Class A: Enemy stats rework. Get that tab up and running. Maybe it's just the bullet speed change but I'm standing around with this one odriscoll shooting at me and he can't even hit me from a few feet away if i just walk constantly. Not even move, just walk.
	Class B: Make it so you can interact with water pumps to drink from them. If/when we get water canteens working, you can refill your canteen from them as alt-interact. If/when we get water pump drinking working, createa custom map icon for them and put them all on the map. 
	</Processing>
	
	<Class_A>
		170. PRONE — CLAUDE HANDOFF — finish the reference-derived implementation
		and validate it in-game; do not return to animation-name/timer guesses.
		Code is in `GameplayTweaks/script.cpp` from
		`// ---- Camera-relative prone locomotion (#170)` through `updateProne`;
		config is `[Prone]` in `GameplayTweaks/GameplayTweaks.ini`; live evidence is
		`GameplayTweaks.prone.log` beside RDR2.exe. Full Ghidra output for Dive -
		Crawl N' Gun is `_analysis/reference-decompilation/Dive-Crawl-N-Gun.c`;
		its read-only package is `_downloads/crawl-n-gun-reference/`. Run
		`python tools/reverse-engineering/verify_prone_
		_parity.py` before every
		build. Do not ship reference binaries, assets, code, or wholesale values.

		FOUR ENGINE TRAPS THAT CAUSED MOST OF THIS SESSION'S FAILURES. Every one
		produced a "nothing changed" or a new visible bug, and each was found only
		by reading the logs. Check these FIRST when an animation misbehaves:
		  1. RDR2 HAS NO TASK_PLAY_ANIM FLAG 2. Rockstar's 1910 call sites use
		     0, 1, and rarely 5/16389/67108864/67108880. A clip issued with 2
		     never starts, and `_GET_ENTITY_ANIM_CURRENT_TIME` then returns 1.0
		     for it, so every phase gate completes on its first frame.
		  2. NEVER GATE ON A LOOPING CLIP'S PHASE. Comparing phase to a threshold
		     to decide "has this started" re-fires once per loop. The climbing
		     grip loops ~14 s, so a 0.35 gate killed movement for ~5 s of every
		     14. Use a time latch for one-shot decisions; phase is only valid for
		     one-shot clips.
		  3. NEVER RE-ISSUE TASK_PLAY_ANIM WHILE A CLIP IS RUNNING. Re-issuing on
		     a per-frame predicate restarts it at phase 0 forever, which looks
		     exactly like a frozen pose. `IS_ENTITY_PLAYING_ANIM` is not a
		     reliable re-issue condition here.
		  4. ANY STATE WRITE THAT BYPASSES setProneState IS INVISIBLE IN THE LOG.
		     Two separate silent writers desynced the prone state machine from the
		     ped for hours (a stale settle timer, and the stance capture firing on
		     presses made while already prone). If behaviour contradicts the log,
		     grep for direct `g_proneState =` assignments first.

		REQUIRED, NOT OPTIONAL — PRONE AIMING AND EQUIPPING. Aiming, firing,
		equipping a weapon, opening the wheel/satchel and raising binoculars all
		currently stand Arthur up, play a standing clip, and drop him back down.
		The cause is that those tasks have no prone form in our implementation, so
		either the input is blocked (dead keys) or he stands. BOTH are wrong and
		both were rejected in testing. Dive - Crawl N' Gun solves this and the
		clips are already identified in its string table:
			`ai_getup@aim_from_ground@cop@pistol@on_back`
			`ai_combat@aim_sweeps@cowboy@grounded@base@1h`
			`mech_climb@upperbody@rifle` (`offhand`, `dual`)
		Implement grounded aim/equip using those dictionaries instead of yielding
		the skeleton or suppressing the control. Cross-check against
		`_analysis/reference-decompilation/Dive-Crawl-N-Gun.c` for the flags and
		the weapon-group selection (`_IS_WEAPON_PISTOL` / `_IS_WEAPON_RIFLE` /
		`_IS_WEAPON_REVOLVER` / `_IS_WEAPON_SHOTGUN` etc. are all called there).
		Until this exists, `[Prone] BlockActionsWhileProne` only blocks AIM,
		ATTACK and RELOAD; everything else stands him up. Do not ship the feature
		claiming completion while this is outstanding.

		LONGARMS ARE THE HARD CASE — USE ROLL-TO-BACK, NOT AN UPPER-BODY HACK.
		Rockstar authored NO two-handed grounded aim sweeps: the only
		`aim_sweeps@...@grounded` dictionaries are `@1h`. This is why longarms are
		broken prone in Dive - Crawl N' Gun; it is an animation-coverage limit,
		not a mod bug, and no amount of flag tuning fixes it. The complete
		authored path that DOES exist is to roll onto the back for long arms:
			face-down -> face-up  `ai_getup@directional@transition@prone_to_faceup`
			                      (back, back_armsdown, back_hipl, back_hipr,
			                       left, right - pick by roll direction)
			back -> face-down     `ai_getup@directional@transition@prone_to_facedown`
			                      (front, front_hipl, front_hipr, left, right)
			crawl while on back   `mech_crawl@base` -> `onback_fwd`, `onback_bwd`
			                      (face-down equivalents are onfront_fwd/bwd)
			longarm aim on back   `ai_getup@aim_from_ground@cop@rifle@on_back`
			                      intro_0/90l/90r/180l/180r, sweep_high/med/low,
			                      fire_0_additive, aim_breathe_additive, and
			                      matching outro_* per intro
			pistol aim on back    `ai_getup@aim_from_ground@cop@pistol@on_back`
		Intended behaviour: face-down crawl is the default; raising a long arm
		rolls Arthur onto his back and drives the on-back aim rig; lowering it
		rolls him back to face-down. One-handed weapons can stay face-down using
		the `@1h` grounded sweeps. Pick the intro/outro variant from the aim yaw
		relative to the body, hold the matching sweep, and layer the fire and
		breathe additives - it is a directional blend rig, not a single clip.

		Confirmed reference mechanics now implemented: ordinary Ctrl entry forces
		crouch, then plays `mech_crawl@base/idle2stealth`; keyboard flags are
		`0x00010C00`, controller flags `0x20010C00`; all crawl calls use task filter
		`0x02000000`; idle flags are `0x30000401`; walk/turn flags are
		`0x30001C01`. Exit uses
		`ai_getup@directional_sweep@combat@cop@rifle@front/get_up_0` with
		`0x20002C10`, waits 600 ms, forces crouch, clears secondary, then clears
		primary with both transition booleans. Dictionary requests are
		existence-checked and throttled instead of spammed every frame.

		Latest built build (2026-07-29) SHA-256 is
		`9A93D836EB38DD9406C2D8D783E04304387268C07F77A9A3FB2344A6514304B6`;
		deployment is queued in `DeployWatcher.ps1` because RDR2 locked the loaded
		preceding ASI; project/game INI hashes match. It removes all manual
		input-derived prone velocity (retaining only an idle momentum clear): the
		reference uses animation root motion, and
		our extra velocity caused W to travel forward-right and idle to slide
		backward. `[Prone] MoveSpeedMultiplier=1.0` now hot-reloads in range
		0.25-3.0 and scales the active walk/turn clip with
		`_SET_ENTITY_ANIM_SPEED`. It also yields the full-body crawl task during
		weapon-wheel selection, aiming/firing/throwing, and hold-Q binocular use;
		a task-ownership handshake clears prone before binocular equip so it does
		not immediately cancel the new binocular task. These changes compile and
		pass 11 static invariants but have NOT yet been tested in-game.

		Last observed defects before that build: W moved diagonally forward-right;
		idle slid backward; holding Ctrl floated Arthur upward then returned him to
		prone; tapping Ctrl shifted the camera as if crouching but left him prone;
		revolvers could not equip; dynamite could not equip or throw; hold-Q put
		binoculars in his hand and showed the Backspace prompt but never entered
		the binocular view. Treat the new build as a proposed fix for each, not
		confirmation. If native weapon actions now function but visibly stand
		Arthur up, port the reference's weapon-category branches and armed-prone
		clips from the full decompilation instead of suppressing the action again.

		The 2026-07-29 build also removes `PLAYER_CONTROL_ON` from the prone
		interruption gate: Rockstar temporarily clears it while the weapon/satchel
		wheel is open, and our gate was explicitly running the prone exit whenever
		anything was equipped. Pistols, revolvers, and throwables now use the
		reference's authored
		`ai_combat@aim_sweeps@cowboy@grounded@base@1h`
		`aim_med_0_intro` -> `aim_med_0` -> `aim_med_0_outro` path with flags
		`0x10000410`; Aim/Attack/Reload are no longer globally disabled.
		`BlockActionsWhileProne=0` is installed. This passes 13 static invariants
		but still needs one in-game pass for equip/draw, aim-camera ownership,
		firing, reload, dynamite throw, and return to crawl. The same installed
		The first longarm/binocular roll-to-back implementation was rejected
		in-game: Aim flickered under the scripted full-body task, the fixed
		`sweep_med` clip did not follow the reticle, rifle aiming repeatedly rolled
		Arthur back and forth through the ground, and binocular holds visibly
		contorted him before the native view. Both timer-only rigs are disabled in
		the installed follow-up. Binoculars now suspend crawl and yield directly
		to the already-working native binocular lifecycle. The weapon/satchel wheel
		returns before prone disables movement/look axes, because the prior build
		left `GET_CURRENT_PED_WEAPON` unarmed after handgun selection. Grounded
		weapon aiming/firing is still ACTIONABLE and requires a native aim-task/IK
		path, not fixed sweep animations.

		The next test logged successful wheel selection/commit, but proved the
		decoded `script_common@other@unapproved/prone_michael` interpretation was
		wrong: it produced an invisible rifle pose, disabled firing/movement, and
		only allowed scripted heading changes. It is a specific full-body scene,
		not a generic prone equipment bridge, and is removed from the active path.
		Wheel closure now commits the chosen weapon without replacing the crawl
		skeleton. Actual prone weapon aim/fire/IK remains unsolved. The same test
		proved immediate task clear exposes a one-frame standing pose on tap-Ctrl;
		tap now retains crawl ownership until the authored prone-to-knees exit is
		streamed. Standing exit no longer forces crouch for 900 ms after
		`get_up_0`, eliminating the erroneous stand/intermediate/stand cleanup.

		Required controls: tap the remappable Duck action for ordinary crouch; hold
		it (default 500 ms) to enter prone; in prone, tap Duck to finish crouched
		and hold Duck to finish standing. Starting crouched must never toggle
		standing before entry. Standing/Crouched -> Prone and Prone ->
		Crouched/Standing must remain continuous and visibly pass through the
		appropriate crouch/kneeling poses. Keyboard/gamepad behavior must match.

		Acceptance: clean launch and repeated transitions from both starting
		stances; no standing pop, float, camera-only false exit, native Ctrl
		interference, stuck task, crash, or A-pose. W/A/S/D must travel in their
		expected camera-relative directions with gradual turning; idle must remain
		still; multiplier 0.5/1.0/1.5 must visibly scale root-motion speed without
		foot/crawl sliding. Verify revolver selection, aim, fire, reload, holster;
		long guns; dynamite equip/aim/throw; binocular hold/use/release/weapon
		restore; scopes; weapon wheel; and unarmed/melee exclusions. Also test
		water, mission/input restrictions, ragdoll, fall, mount, vehicle, ladder,
		death, save/load, teleport, ASI restart, slopes, and climbing conflict.
		Update this entry and `AGENTS.md` only from observed results. X

		175. STEALTH SYSTEM AUDIT AND REWORK — CLAUDE HANDOFF — finish the
		engine-owned visual-detection investigation, replace the failed temporary
		test workflow, and use the proven result to finish the LEXEDITOR design.
		Start with `docs/STEALTH_SYSTEM_AUDIT.md`; perception/noise data is already
		exposed under LEXEDITOR's AI tab. `pedperception.meta` records are shared
		profiles, not one record per ped model. Do not invent a universal detection
		meter or per-model stealth stats without runtime evidence.

		Existing probe files are `StealthProbe/script.cpp`, `main.cpp`, `QUESTS.md`
		and `README.md`; the installed temporary build/logs are beside RDR2.exe.
		It logs nearby entities at 20 Hz: distance, facing, LOS,
		`IS_TARGET_PED_IN_PERCEPTION_AREA`, suspicion/fear/anger/agitation/bravery
		motivations, relationship, combat/flee/melee, task statuses, threat/events,
		and player stance/movement/weapon state. Audit every native/task hash and
		parameter before trusting a constant zero or task status 8. Decompiled SP
		scripts are `_downloads/RDR2-Decompiled-Scripts/script_rel`; search the
		complete native surface with `_downloads/grep_natives.py`, not only the
		incomplete SDK `natives.h`.

		Confirmed evidence: refinery guards could report perception/LOS for about
		14 seconds with all logged motivations and combat still zero. Roughly 24
		seconds after the next marker, three guards' anger jumped from 0 to 1
		simultaneously although only one had LOS and another faced away; one entered
		combat immediately. This is shared trespass/encounter escalation, not proof
		of an individual visual meter. The Lemoyne Raiders base likewise uses a
		spoken warning followed by synchronized hostility. Bounty hunters are
		search-and-flank AI and cannot serve as stationary observers.

		The attempted F10 controlled observer also failed acceptance. Its first
		build used a wrong model hash. The corrected `A_M_M_VALTOWNFOLK_01`
		(`0x838F50CE`) entities existed according to the log at 19–20 metres with
		full LOS/perception, but were not visible to Lexer. Repeated F10 presses
		created/deleted valid handles; exposed samples remained at zero anger and
		combat. Do not infer stealth behavior from this: placement/view direction,
		outfit/render readiness, freezing, `TASK_STAND_STILL`, and synthetic
		relationship hostility are all possible contaminants. Remove or replace
		this harness rather than layering more guesses onto it.

		Lexer has Rampage and explicitly suggested using its proven spawn/control
		facilities. Inspect its available ped spawn, placement, relationship,
		stationary/freeze, task, invincibility and reset controls, or reproduce only
		the necessary mechanism in this disposable ASI. A replacement harness must
		be visibly self-verifying before any experiment: put the observer at an
		aimed/camera-visible grounded coordinate, dress/render it, mark it visibly,
		display its handle/model/distance/LOS/state on screen, provide one-button
		reset, and record the complete experiment automatically. Never again make
		Lexer locate a supposedly suitable encounter, manually install a build,
		repeat one-variable launches, or follow a long checkbox sequence. Validate
		the harness independently as far as static/API inspection permits, then ask
		for at most one short in-game session that captures every remaining case.

		Resolve with evidence: whether qualified visual exposure accumulates across
		interrupted peeks or requires continuous visibility; the exact role and
		reset behavior of `MovementDetectionTime`; whether any hidden value decays;
		how unaware, orient/investigate, search, flee and combat transitions differ
		from witness suspicion; how distance, FOV, LOS, stance, movement, lighting
		and noise feed those transitions; and the separate unalerted/alerted/flee/
		warn/charge animal path. Identify which controls are global, shared
		perception profiles, scenario/script-owned, relationship/event-owned, or
		engine-owned.

		Acceptance requires: reproducible timestamped evidence for continuous and
		interrupted exposure, loss/reacquisition, investigation/give-up, hostile
		escalation and prey/predator responses; a settled correction to
		`docs/STEALTH_SYSTEM_AUDIT.md`; durable facts updated in `AGENTS.md`; and
		LEXEDITOR exposing only genuinely editable controls with Human/Animal
		grouping when supported by the actual data ownership. Keep TODO 111
		dependent on this result. X

		169. SURFACE-CONFORMING FREE CLIMBING — CLAUDE HANDOFF — finish and
		validate this independently from TODO 170 Prone. Required entry behavior:
		(1) replace the vanilla slipping state automatically when Arthur begins
		sliding backward on terrain too steep to walk; (2) at a non-sliding solid
		obstacle, require Forward + Jump, allow Rockstar vault/mantle first refusal,
		and enter custom climbing only when native traversal fails; (3) allow
		midair contact/re-grab. Merely walking into a cover-height or ordinary
		impassable object must never auto-climb or steal Cover.

		Required traversal: continuously conform to changing collision rather than
		holding one initial plane; support irregular cliffs, convex/concave corners,
		lateral wrapping, camera-relative surface-tangent movement, sprint climbing,
		directional sprint-leaps, outward wall-jumps, midair re-grab, native top-out,
		and release on lost contact or empty outer Stamina without spending the
		Stamina Core. Exclude missions initially, plus interiors, cutscenes, melee,
		scripted tasks, mounts/vehicles, ladders, water, ragdoll, and death. Keyboard
		and gamepad must share behavior. Keep `[Climbing]` settings hot-reloadable
		and one comprehensive development trace enabled by default.

		Current reference-derived implementation is isolated in `GameplayTweaks/script.cpp`
		from `// ---- Surface-conforming free climbing (#169)` through
		`updateClimbing`; config is `[Climbing]` in
		`GameplayTweaks/GameplayTweaks.ini`; runtime evidence is
		`GameplayTweaks.climbing.log` beside the installed ASI. Full Ghidra output
		for UFCO is `_analysis/reference-decompilation/UFCO.c`; its read-only backup
		is `_reference_mod_backups/UFCO-20260728-012130`. Run
		`python tools/reverse-engineering/verify_prone_climb_parity.py` before every
		build. Do not copy or ship UFCO code/assets, its treasure system, double
		jump, ragdoll cancellation, or fall-damage exploit. Decompiled Story
		scripts are under
		`_downloads/RDR2-Decompiled-Scripts/script_rel`; use
		`_downloads/grep_natives.py` for the complete native surface before adding
		probes. TODO 187 separately covers temporarily restoring UFCO to review its
		chest locations/contents and must remain separate from this mechanic.

		Full decompilation corrected the central false assumption: UFCO never
		freezes the player; its sole freeze native targets a treasure object.
		The pose is played with the exact tail
		`1.0, 1.0, -1, 1, 1.0, FALSE, 1, FALSE, "", FALSE`.

		Latest built ASI SHA-256:
		`9A93D836EB38DD9406C2D8D783E04304387268C07F77A9A3FB2344A6514304B6`.
		Deployment is queued in `DeployWatcher.ps1` because RDR2 locked the loaded
		preceding ASI; the INI is already synchronized.

		STATE AS OF 2026-07-29 TEST — VERIFIED IN-GAME BY LOG, NOT JUST
		COMPILED. The A-pose is gone and attachment/movement work, but climbing
		held `base_right_hand_up` and visibly slid without a climb animation. The
		cause was NOT the task clear or the cadence. It was the per-frame
		coordinate write: UFCO calls
		`SET_ENTITY_COORDS_NO_OFFSET` with axis flags `1,1,1`
		(decompiled: `FUN_180007840(x,y,z,1,1,1)`), we were passing
		`FALSE,FALSE,TRUE`, and that reset the ped's animation to frame 0 every
		frame. See `SET_COORDS_NO_OFFSET_ALIGNED` - use it on the climbing path
		only; the file's other coord call sites keep the old flags on purpose.
		Confirmed by trace: `animPlaying=1` and `anchor == actual`, but the active
		clip remained the static grip during both ascent and descent. The installed
		follow-up selects `climb_up` for W, `climb_down` for S, and a hand-up grip
		only while idle, without per-frame reissue. Bottom contact now enters a
		`Dismounting` state and retains coordinate ownership until the authored
		bottom-exit clip finishes instead of immediately releasing Arthur inside
		the ground. Both changes compile and pass 22 static invariants but remain
		unconfirmed in-game.

		The 2026-07-29 pole/station tests proved the climb animation advances, but
		the old top-out was false: a missing head contact released physics and
		called native `TASK_CLIMB` without proving any summit, so poles, beams,
		roof undersides, and signs produced falls, through-roof travel, or
		sink/bounce. Entry also accepted one collision hit and averaged unrelated
		normals/entities into imaginary planes. The installed follow-up requires
		three consistent same-entity body contacts on entry (two while attached),
		reduces standoff from 0.55 m to 0.16 m, and disables unauthored A/D
		translation. `mech_ladders`
		has no generic lateral wall-traverse clip. W/S now use the authored
		start/loop/settle clips with input-release hysteresis instead of resetting
		to the base pose on every tap. Top-out now requires a ground landing behind
		and above the lip, retains coordinate ownership through
		`get_on_top_front`, and only releases Arthur after the authored mantle;
		poles/beams with only distant ground remain attached. Full clearance and
		in-game validation remain required.

		TWO INVARIANTS WERE REMOVED FROM THE VERIFIER ON IN-GAME EVIDENCE, DO NOT
		REINSTATE THEM WITHOUT RE-TESTING. The clip genuinely comes from a table
		(`(&PTR_s_base_right_hand_up)[index]`), but nothing proves that index
		changes on a timer - the 700/1000 ms cadence was inferred. Implemented, it
		ran `CLEAR_PED_TASKS_IMMEDIATELY` once a second, which drops Arthur to an
		A-pose and re-blends the grip - reported in play as "strikes the pose,
		instantly jumps back, slowly re-grips, and does it again on every movement
		key". The grip is now issued ONCE per attachment with no per-swap task
		clear.

		STILL OPEN on climbing: in-game top-out validation, an authored lateral
		traversal mechanism, sprint leaps, corners, ledges, and the full acceptance
		list below are untested.

		Acceptance requires an in-game session proving: automatic grab at the exact
		moment ordinary mountain slip begins; Forward + Jump acquisition on a
		near-vertical mountain face only after native traversal fails; no automatic
		grab while taking cover at a rock; sustained controllable movement after
		attachment; irregular/flat surfaces, corners, ledges, trees, poles, fences,
		roofs, overhang rejection, top-out, leaps/re-grabs, contact loss, zero-
		Stamina fall, keyboard/gamepad parity, and every exclusion. No hovering,
		fixed-plane behavior, penetration, ceiling attachment, fall-damage
		cancellation, input theft, or native traversal conflict. X

		186. CAMPSITE MAP 
		 ART — generate and review two distinct,
		RDR2-style monochrome map glyphs for an authored campsite and an activated
		respawn campsite; then register and insert them after the custom map-TXD
		pipeline is proven. Replace the temporary BLIP_CAMPFIRE and
		BLIP_CAMPFIRE_FULL placeholders used by TODO 59.

		185. REDM / CFX REAUDIT OF DROPPED FEATURES — revisit every entry in
		`<Dropped>` against RedM UIApp examples and Cfx's public RDR3-specific
		source before accepting its old feasibility conclusion. Translate usable
		DataBinding paths, UIScript events, native calls, hooks, offsets, graphics/
		CEF techniques, and streaming discoveries into Story Mode C++/ScriptHook
		mechanisms where possible. Distinguish portable Rockstar mechanisms from
		features supplied only by the Cfx runtime, obey source licenses, and move
		each reopened feature into exactly one current TODO section with evidence.

		182. VANILLA-STYLE RECON TAG CORES — replace the temporary drawn glyphs
		with tags matching Rockstar's player-core visual language: black circular
		core, interchangeable inner sprite/state coloring, and an independent
		circular outer health bar. Reuse shipped core/blip texture assets where
		they can be loaded safely; retain a custom renderer for per-entity state.

		177. TAXIDERMY BIRD-CARCASS REMOVAL — determine whether the Wildlife Art
		Exhibition requirements are data- or script-owned, remove its bird-carcass
		objectives, and disable carrying bird carcasses without breaking plucking,
		loot, compendium credit, or mission completion.

		178. HORSEMAN CHALLENGE REWORK — randomize ranks 1–9 per save across the
		specified horseback endurance, bonding, feeding, breaking, combat, timed
		route, revival, and cold-weather horse-state goals. Rank 10 escorts an
		unridden horse across New Austin while recurring wolverines hunt it; award
		the Elk Antler Trinket on completion.

		179. TONIC-TIER CRAFTING AND SHOP UNLOCKS — each tonic-family upgrade
		unlocks crafting and doctor purchase one tier above the family's current
		level. Support parallel upgrade sources, cap at tier 4, and report an error
		instead of producing tier 5.

		61. DARK SOULS-STYLE TONIC CAPACITY REWORK (REQUIRES DS3 STYLE ITEM OVERFLOW FIRST) — give Health, Stamina, and
		Dead Eye tonics configurable upgradeable active capacities. Overflow goes
		to persistent storage; camp visits and death refill from storage,
		highest-tier first, and notify when a full refill is impossible.

		89. CASING CUSTOM ART AND AMMO-ICON REPAIR — preserve loaded ammunition's
		vanilla icons, repair missing icons including .22 and .225 AP, and assign
		custom art only to the .225, .327, and .444 spent-casing ingredients. Make
		the casing trio read as related small, medium, and large centerfire rounds.

		108. MOONSHINE INSTANT KNOCKOUT — make moonshine immediately knock out the
		player so it can support the Guarma-glitch challenge.

		124. BANDIT CHALLENGE REWORK — randomize ranks 1–9 per save and award a
		random unowned mask after each, with the last reward fixed. Restore and
		mask-enable the specified nine head items through #16, count Arthur as
		wanted in New Austin for the every-state objective, implement the weaponless
		city robbery finale and reinforcements, and award a Deputy's Star trinket
		that halves law perception through a proven mechanism.

		131. BELT-MOUNTED LANTERN — remove the lantern from the radial menu, keep it
		on the belt, and light it automatically at night while not crouched. After
		the stealth audit, make its light affect detection if vanilla does not.

		X16. CUT AND BULK
		This is going to be a massive one with many related subtasks with complex dependencies and orders. I want to add in all the Online-only content into Offline so I can use it and test it. Then, I will take this big pool of content and begin cuttint content until everything in the game is fun and serves a purpose/niche -- guns, clothes, items, whatever. This requires, first, the Offline Content Unlocker, except I really don't want requirements for my mod so I want to bundle it in, except I checked the permissions and the mod creator won't allow that, so we'll have to recreate it from scratch, but that only removes whatever blocks it from SP use, so then we need to implement Red Dead Offline in my mod, which CAN be included in other mods, except I think it's a catalog.yml mod so we'll have to recreate its changes from scratch anyway. but I don't even know what from it I'm gonna keep so maybe we should just like, I don't know, is there a list or something I can go through of everything and a way I can just test it out all in game, what even will it be, clothes and guns, anything else? Oh, plus there are lots of mods that add new content that are tough to also combine and can we even add them to ours and will we have to recreate them from scratch and how can we merge them and...omfg where do we even begin with this one?
		Not to mention there are a number of related questions and goals I have related to this:
			-- Time-limited Outlaw Pass items that are no longer even obtainable. These are also in the files like all others, these I can just re-enable without problem?
			-- That bucket helmet from Online. I want/need to add armored enemies. We need to find it and re-enable it. We can do that, right?
			-- Import the Online-only Improved/Refined Binoculars
			(`WEAPON_KIT_BINOCULARS_IMPROVED`) alongside the other RDO content.
			Make them a genuine binocular upgrade through better zoom and/or
			faster recon tagging, rather than a duplicate inventory item.
			-- One of the other todos is tied to this one, moved into this one for convenience's sake: 
				49. BANDIT RANK 4 GLASSES REWORK — import the intended Outlaw Pass glasses
			through the eventual online-item/RDO compatibility work, award them at
			Bandit rank 4, and make wearing them halve the law's active search radius.
			SP currently contains no suitable glasses asset and NativeDB has a wanted-
			radius getter but no setter, so identify a compatible asset and a proven
			script hook before claiming the unlock or effect is implemented.
			
		Also, the following block of text is how GPT describes the task. ~Lex. 

		ONLINE WEAPONS + LEANER ROSTER — bring online-only weapons into SP by
		REQUIRING the existing unlock mods (never shipping their files), then cut
		redundant weapons so each remaining gun is unique and the weapon menu is
		quick to cycle.
		Reference for weapon stat editing: "Realistic Weapon Overhaul"
		(rdr2mods.com/downloads/rdr2/weapons/113) — proves weapons are data-
		editable via LML; crack open to learn which files.
		Compatibility warning: Red Dead Offline integration is unusually hard;
		weapon/item mods commonly need a custom RDO-compatible merge rather than
		loading independently. Weapon Rebalance publishes custom compatible
		versions, so inspect those merges when this work starts.
		Additional item source to consider while expanding then pruning the roster:
		The Trifecta - Redux (Nexus 3639), alongside Red Dead Offline. Red Dead
		Offline advertises broad RDO weapon/item/vendor imports, but does not prove
		that every time-limited Outlaw Pass item is included. When sourced, inspect
		its catalog, shop inventories, meta-ped assets and strings specifically for
		Outlaw Pass eyewear (needed by Bandit rank 4), then identify a second source
		or build a compatible import if those glasses are absent.

		38. REWORK WEAPONS, WEAPON STATS, AND WEAPON MODS — I want to rework the weapon mods, maybe even make new ones, but I was looking at the improved accuracy from the improved iron sights and you said that changing it would only change the DISPLAYED change and not the actual change so we need the editor to be able to show and change both actual and displayed changes together but I think you also said that weapon stats aren't even single quantifiable values and the displayed values in the UI are actually just rough approximations of a number of other stats or something?

		111. (Req. 175) STEALTH INDICATORS — Stealth indicators -- either FC3 style or MGSV style, depending on how the game handles stealth. Will have to explore.

		168. DARK SOULS-STYLE CONTINUOUS SAVING / NO MANUAL LOADING — remove the
		ability to manually load an earlier save during normal play and make
		meaningful state persist automatically so quitting cannot erase
		consequences. Audit Rockstar's native save triggers and every mod-owned
		persistence file, then autosave changes to money, inventory, health/cores,
		crime/bounties/honor, deaths and lost money, challenge progress, world
		pickups, merchants, camps, and other durable world state. Handle death,
		arrest, mission failure, crashes, forced mission checkpoints, and save-slot
		migration without corrupting saves or trapping the player in a broken
		state. Keep an explicit recovery/debug escape hatch outside ordinary
		gameplay, but no player-facing reload-to-undo loop.

		159. FUCK CRAFTING WE HAVE SO MUCH FUCKING WORK TO DO FUCK MY LIFE MAN
		Making my breakdown recipes requires us to create a custom crafting menu to remove the single output restriction and other crafting restrictions. There's a crafting menu mod I have installed as well as an RDR2 menu creator github project to exist as prior art. IG we'd have to make it show both my "impossible" recipes and vanilla ones, and replace the vanilla crafting menu everywhere it's seen...as we'll need some kind of data storage for our "impossible" Recipyes since they'll have to be seperate from vanilla ones...must be editable in lexeditor, obviously.
		MELT DOWN GOLD / SILVER / PLATINUM INTO BASE METALS — let jewellery and
			precious-metal valuables be broken down into base metal for crafting (gold
			ring/necklace/earrings/bracelet -> gold, etc.).
			THE "4 RECIPES PER ITEM" WORRY DOES NOT APPLY — findings 2026-07-24:
			  - Vanilla catalog data has a MAXIMUM OF 1 crafting recipe per output item
				(measured across the whole catalog: 255 craftable items, all exactly 1).
				So "4" is not a vanilla data limit; the concern came from elsewhere.
			  - Our Breakdown feature does NOT use catalog recipes at all. The ASI writes
				recipe rows straight into the live CraftingDatastore each frame
				(updateBreakdownCrafting): DB_ADD_LIST(store,"recipes") then per row
				DB_ADD_HASH "name", DB_ADD_INT "eOutputItem", "eCost"=COST_CRAFTING and
				"iNumCostVariants". LEX_GUNPOWDER has ZERO COST_CRAFTING entries in
				catalog_sp.ymt yet runs 5 variants, proving the recipe is entirely
				runtime-defined and not bound by the catalog's per-item structure.
			=> TWO levers, both unlimited in practice: (a) more cost VARIANTS on one
			recipe row (iNumCostVariants), and (b) more recipe ROWS for the same output.
			So we can add a row per source item ("Melt Gold Ring", "Melt Gold Necklace")
			or one row per metal with many variants — whichever reads better in the menu.
			WORK: define base-metal items (gold/silver/platinum) if they do not exist,
			decide yields per source item by value/weight, extend breakdown_recipes.csv
			(or its successor) to express input->output, and confirm the menu lists them
			all without truncating. Watch for a UI-side display cap even though the data
			side has none.
			
		150. MAP: JUMP TO PLAYER — in the map screen, pressing L3 (left-stick click) or
		MMB (middle mouse) recenters/jumps the map view to the player's current
		position. Detect the map/pause-map screen is open, read the input (L3 via
		XInput LEFT_THUMB like the binocular pad button; MMB via GetAsyncKeyState
		VK_MBUTTON 0x04), and move the map cursor/camera to the player's world coords.
		Find the native that sets the map/waypoint cursor or pans the pause-map to a
		coordinate (investigate; may need the map-cursor / _SET_..._MAP natives). If
		no direct native, the probe approach can help identify the panning control.
		WAIT NO NOT L3 I think that one's taken? If so R3
		
		147. COLLECTIBLE MARKERS — UNIFIED DESIGN (Lexer's, 2026-07-24)
			IMPLEMENTED 2026-07-28: enabled categories become visible only after their
			associated quest/document unlock; custom icon registration is independent.
			Known-bad POIs are disabled. Native carving found-state remains authoritative
			and proximity-only clearing remains disabled. Remaining work below is
			collected-state/world-model precision for the other categories.
			Every marker is one record: { type, isCollected, worldModel?, coords }.
			Three independent problems per category: (A) where it is, (B) how we know it
			is collected, (C) does it need a world model. Mod targets NEW SAVES, so our
			own persisted state is acceptable where the game exposes none.

			CONFIRMED TOOLING:
			  - COLLECTABLE API: _COLLECTABLE_CATEGORY_GET_NUM_COLLECTABLES 0x62CAB7DB62EAD434,
				_GET_COLLECTABLE_ITEM_HASH 0x126CBEBBA46693CF,
				_GET_PLACEMENT_LOCATION 0x1F1DD794908C2BFA, _GET_NUM_FOUND 0xF83D3DDA4D3C8169.
				Populated in SP: CIGARETTE_CARDS(144), DINO_BONES(30), ROCK_CARVINGS(10),
				LEGENDARY_FISH(14). Only ROCK_CARVINGS returns real coords; others 0,0,0.
			  - ScriptHook exposes worldGetAllObjects / worldGetAllPickups / worldGetAllPeds
				(SDK main.h) -> enumerate loaded entities, read models via GET_ENTITY_MODEL.
				This is how we LEARN worldModel hashes empirically AND how the one-time
				map-scan harvest works (grid-teleport on a blank save, dump model+coords).
			  - COMPENDIUM: GANG_HIDEOUT_FOUND / GANG_CAMP_FOUND / ANIMAL_SET_DISCOVERED /
				GET_ENTRY_BY_STAT_ITEM -> animal + hideout progress (getters TO VERIFY).
			  - GET_CLOSEST_OBJECT_OF_TYPE 0xE143FA2249364369 (needs a model hash).

			PER-CATEGORY PLAN (coords | isCollected | worldModel):
			  Rock carvings   NATIVE coords | NATIVE per-item found | not needed  -> DONE/built
			  Cigarette cards SCAN harvest  | NATIVE per-item found | yes (scan)  -> best case
			  Dino bones      SCAN harvest  | NATIVE per-item found | yes (scan)
			  Legendary fish  manual/area   | NATIVE per-item found | none (no prop)
			  Legendary animals area/manual | COMPENDIUM (verify)   | none (ped, _GET_ANIMAL_RARITY)
			  Gang hideouts   SCAN/manual   | COMPENDIUM hideout    | n/a
			  Shacks          SCAN harvest  | distance, SMALL radius| optional
			  POIs            SCAN harvest  | distance, SMALL radius| optional
			  Graves  (WANTED)SCAN harvest  | distance, SMALL radius| optional
			  Dreamcatchers   SCAN harvest  | distance / object gone| yes (scan)
			  Treasure maps(W)SCAN harvest  | distance              | n/a
			  Exotics(235)    -> moved to WAITING (Algernon flowers; Lexer may not want it)

			*** SOLVED 2026-07-24: THE SOURCE DATA WAS FINE, OUR CONVERSION WAS MISCALIBRATED ***
			build_collectible_locations.py used x=31.4942*lon-1002.46, y=44.8413*lat+1137.75.
			Fitting the 10 scraped carvings onto the game's 10 native carving coords (ICP,
			all 10 matched distinctly) gives a correction: x'=1.051014*x+90.68,
			y'=0.774834*y+3.09 -> residuals min 2.1 m, MEDIAN 6.2 m, max 22.8 m (was
			median 342 m). Corroboration that this is real and not overfitting: the fix
			makes the two axis scales nearly equal (33.1 vs 34.7) as a real projection
			should be; the original Y scale was ~22% wrong. ALL 576 markers in
			collectibles.csv have been recalibrated (backup: collectibles.csv.uncalibrated)
			and AutoClearOnReach re-enabled with ClearRadius=20.
			=> THE GRID-SCAN HARVEST IS NO LONGER REQUIRED FOR COORDINATES. It is only
			worth doing if we later want sub-metre precision, or worldModel hashes for
			"object is gone" clearing on categories with no native found-state.
			If a category still looks off, refit using more ground truth rather than
			assuming the source is bad.

			(superseded) earlier finding:
			Compared all 10 scraped carving coords against the game's native carving
			coords (nearest-neighbour, 2D): error min 41 m, MEDIAN 342 m, max 537 m. A
			342 m error is not "slightly off", it is the wrong area entirely. Therefore
			NO category can reuse the CSV positions — not even big targets like shacks —
			and the grid-scan harvest is REQUIRED for every category except rock
			carvings. Do not resurrect the CSV or proximity-clear against it.

			IDENTITY / MAPPING (Lexer's question, answered 2026-07-24): clearing the RIGHT
			card icon only needs an index-to-coordinate mapping if we clear via native
			per-item state. Positional clearing does NOT need identity at all: the marker
			you walked to is the marker we remove. Confirmed the game DOES identify cards
			individually — probe shows exactly 11 found at scattered indices (13,30,38,56,
			66,72,79,90,122,132,133), matching the category count.
			SELF-BUILDING MAPPING (preferred, no manual work): when a card is collected we
			know both halves — the nearest marker, and the native index that just flipped
			not-found -> found. Persist that pair. The map builds itself over a playthrough
			and each pair is self-validating. Once mapped, upgrade that category to native
			per-item clearing (robust even for cards obtained without visiting a marker,
			e.g. during missions). The 11 already-found indices cannot be learned this way.
			Also worth testing: whether native index order matches the card-set order in
			our scraped names, which would give the whole mapping instantly.

			KEY MECHANIC (Lexer): for anything with a worldModel, the honest collected
			test is "player is very close AND the object is no longer there" — not blind
			proximity. Check only the nearest marker to keep it cheap.
			NEXT: (1) probe worldGetAllObjects/Pickups next to a known card/bone/dreamcatcher
			to capture model hashes; (2) write the grid-scan harvester; (3) map harvested
			coords to COLLECTABLE item indices so per-item native clearing applies.
			
		146. SELLING MODEL + SHOPS TAB REDESIGN
		*** EVIDENCE 2026-07-24: PDATA_SHOP_INVENTORIES IS NOT A SELL WHITELIST ***
		Inspected the runtime vanilla dump. The lists are almost entirely AMMUNITION:
		ST_GENERAL 5 (all ammo), ST_GUNSMITH 8 (all ammo), ST_TRAPPER 11 (split-point
		ammo + herbs + 1 alligator tooth), ST_FENCE 228 (explosives/express ammo +
		unresolved hashes). DECISIVE: the trapper list contains NO pelts or carcasses,
		yet trappers demonstrably buy them. Therefore this structure is a narrow
		per-item OVERRIDE/exception list (mostly making ammo sellable), NOT the master
		record of what each merchant accepts. Unchecking a shop in the editor cannot
		stop the player selling something — which is what Lexer actually wanted.
		Editor help text corrected to say so.
		CONFIRMED 2026-07-25: shop scripts calculate payout with
		_ITEM_DATABASE_FILLOUT_SELL_PRICE(item, joaat("SELL_SHOP_DEFAULT"), ...).
		Removing that acquire-cost is the data-driven global unsellable switch.
		PDATA checkboxes are now labelled as explicit exceptions rather than
		pretending unchecked means rejection.
		REMAINING WORK: map each compiled shop's ordinary category/tag acceptance
		rules into a read-only effective-acceptance report. Per-merchant denial of
		one otherwise sellable item has no identified data field and needs a
		shop-script/runtime hook before LEXEDITOR can truthfully offer that control.
		
	139. COMBINE PARTIAL ITEMS — add crafting recipes that combine used or partial
	    versions of the same consumable into complete items. Inventory and recipe
	    logic must account for the amount remaining in each variant, require an
	    equivalent full item's total contents, preserve containers where relevant,
	    and prevent combining incompatible item types or strengths.

	136. EXPLOSIVE-AMMUNITION FIRE / EXPLOSION VFX — i might have accidentally removed some tags or FX on the exploding ammo to make it less splodey. unbreak those

	103. COLLECTIBLE EMPTY BOTTLES — CLAUDE HANDOFF; FAILED IN-GAME TWICE
	    2026-07-28. Drinking Guarma Rum produced no inventory bottle, feed, or
	    physical collectible. The latest `GameplayTweaks.empty-bottles.log`
	    contains no Rum event at all (only the older Brandy line), proving the
	    `_USED` inventory-delta detector does not cover this consumption path.
	    `NEVER_DROP` also does not create a collectible: it left no bottle on the
	    ground. Replace both assumptions. Trace `generic_alcohol_item.c` and the
	    actual inventory GUID/count transitions for full and `_USED` whiskey,
	    brandy, gin, and rum; log all four before implementing the grant. If the
	    desired physical bottle cannot survive the interaction, explicitly spawn
	    a pickup/object at the final-swig position and use the proven casing-style
	    collection prompt. Grant Rockstar's existing `PROVISION_EMPTY_BOTTLE`,
	    then prove its inventory count, feed, icon, recipes, cap, and persistence.
	    `[EmptyBottles] HumanTonicBottles` controls every
	    human Health Cure, Bitters, Snake Oil, and Miracle Tonic together and
	    defaults off. The project already has this bottle record, a custom icon,
	    five-item satchel capacity, and normal/volatile fire-bottle recipe inputs,
	    so the earlier instruction to create `LEX_GLASS_BOTTLE` was wrong.
	    `iteminteractioninfo.meta` applies `NEVER_DROP` to all 24 relevant
	    PropData-owning alcohol/single-use bottle states. `LEX_WATER_BOTTLE`
	    costs one empty bottle, restores 25% Stamina Core, and appears through
	    the runtime crafting datastore; normal and volatile fire-bottle recipes
	    already consume the canonical bottle. Confirm the four liquors, the one
	    tonic-family switch, no discarded prop/smash, both fire-bottle recipes,
	    water crafting/consumption, icon/feed, capacity, and restart persistence.

	    2026-08-03 ROOT TRACE: `generic_alcohol_item.c` applies each swig on the
	    authored animation event `442509369`; every full and `_USED` inventory
	    alcohol record is independently consumed in one swig. The prior build's
	    false "full becomes used first" check therefore ignored Kentucky Bourbon.
	    Its live log proved inventory count drops while the interaction is still
	    running. The ASI now preloads, interrupts at that proven post-swig
	    inventory transition, and plays
	    `mech_inventory@item@_templates@cylinder@d6-5_h1-5_inspectz@unarmed@base`
	    / `cylinder_put_away_satchel`, and grants `PROVISION_EMPTY_BOTTLE` at the
	    hand-to-satchel point. The authored event remains logged as corroboration;
	    guessed `DISCARD` hashes remain rejected. Full restart and in-game
	    confirmation are required.

	    OBTAINABLE DRINKABLE BOTTLES (verified in catalog; all loot-only, none
	    buyable). Internal key -> in-game name -> world model:
	      CONSUMABLE_WHISKEY  -> "Kentucky Bourbon" -> S_INV_WHISKEY01X
	      CONSUMABLE_BRANDY   -> "Fine Brandy"      -> S_BRANDY01X
	      CONSUMABLE_GIN      -> "Gin"              -> S_INV_GIN01X
	      CONSUMABLE_RUM      -> "Guarma Rum"       -> S_INV_RUM01X
	    EXCLUDE: CONSUMABLE_MOONSHINE (model S_INV_FLASK01X is a flask, not a bottle).
	    Human tonics are controlled together by the one INI switch above.
	    Vanilla already ships EMPTY-bottle props (used by the _USED half-drunk
	    variants): P_BOTTLEJD_USED01X (whiskey), S_BRANDY_USED01X, S_INV_GIN_USED01X,
	    S_INV_USEDRUM01X. Reuse these rather than the full model.
	    `PROVISION_EMPTY_BOTTLE` is the existing canonical generic bottle.

	    TWO APPROACHES (owner leans toward B if the anim can be cut cleanly):
	      A. Let him throw the bottle, suppress the smash, spawn a collectible
	         bottle where it lands. REUSES the SpentCasings pipeline wholesale
	         (CREATE_OBJECT -> UIPrompt on INPUT_LOOT -> INVENTORY_ADD -> feed icon
	         -> bend-down anim; see updateSpentCasings / CASING_PROMPT_* in
	         GameplayTweaks/script.cpp).
	      B. Cut the drink animation before the throw and swap in the
	         put-into-satchel ending, then auto-add the bottle. Cleaner (no sound to
	         suppress) but depends on the throw being a separate clip we can skip.

	    SETTLED: the drink is an item-interaction state machine; the discard is
	    engine/interaction driven rather than a standalone script throw. Dicts are
	    keyed by
	    bottle SHAPE, only four dicts:
	      MECH_INVENTORY@DRINKING@BOTTLE_CYLINDER_D1 / BOTTLE_OVAL_L5 /
	      BOTTLE_OVAL_L6 / BOTTLE_RECTANGLE_L4
	    RDR2 has no native to enumerate a dict's clips, so it must be probed at
	    runtime or opened in OpenIV/CodeWalker.

	    OWNER OBSERVATION (important): one drunk bottle broke, another did NOT. The
	    glass-smash is therefore probably the thrown prop's PHYSICS/collision audio,
	    not an animation event — meaning (a) there may already be a real bottle
	    entity in the world to attach a prompt to, and (b) there is no audio event
	    baked into the .ycd to strip out. Verify: does breakage track ground surface
	    (hard vs soft) or is it random?

	    NOTE ON ANIM EDITING: the "Extended Player Animations" mod
	    (D:\Downloads\Extended Player Animations-...rar) does NOT author or edit
	    animation data. It swaps whole existing .ycd files (MP->SP) via LML file
	    replacement and edits anim-SELECTION metadata (clip_sets.ymt, motions.ymt,
	    directswap.meta, human_male.ymt). It contains zero drinking/bottle content.
	    So "just edit the anim to cut the throw" is not supported by it; trimming a
	    clip would mean authoring a .ycd, for which RDR2 tooling is immature. Prefer
	    the script route (interrupt the task, play a second clip) over editing .ycd.

	    PROBE STATUS (2026-07-21): a read-only [BottleProbe] block was added to
	    GameplayTweaks (updateBottleProbe in script.cpp, ini section BottleProbe).
	    It logs which drink clip is playing + nearby bottle props to
	    GameplayTweaks.bottle.log. NOT YET RUN SUCCESSFULLY: first build used GTA5
	    native hashes for IS_ENTITY_PLAYING_ANIM / GET_ENTITY_ANIM_CURRENT_TIME that
	    don't exist in RDR2 (would have logged nothing). Now fixed to the SDK
	    wrappers (ENTITY::IS_ENTITY_PLAYING_ANIM 0xDEE49D5CA6C49148,
	    ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME 0x627520389E288A73) plus a 10s
	    heartbeat so "no clip matched" is distinguishable from "probe never ran".
	    Rebuilt + installed 2026-07-21 but re-DISABLED (Enabled=0) pending a run.
	    NEXT STEP: enable the probe, drink a Kentucky Bourbon, read the log to see
	    the clip name(s) and timings — that answers the A-vs-B question. The clip
	    candidate list in updateBottleProbe is a GUESS; if only a heartbeat appears
	    with no clip line, the drink isn't driven by a ped anim task and B is dead.

	91. WANTED-LEVEL DURATION AND SEARCH AREAS — How do I edit how long wanted levels last, how big wanted circles are, and how long it stays in that state afterwards where the wanted circle is gone but the cops are dark red dots on the map and if they see you they'll hunt for you again? I want to make those all last a way longer time, let me csustomize them in the editor. So you commit some big crime and you basically can't return to that area for ages. You commit multiple big crimes in different places in quick succession and every time you open up the world map you'll see these big places you can't return to right now.
	
	94. WALLET SIZE CAP — FEASIBLE through the ASI, not catalog data. Add an INI
	    cap and message, enforce the cap at every known cash acquisition path, and
	    connect its rank to Gambler progression. Balance polling can clamp ordinary
	    gains but briefly accepts the money and may allow side effects; release
	    quality requires intercepting the central cash-add native/script path and
	    testing loot, sales, missions, gambling, mail, and scripted rewards.
		
	95. MAP REVEAL BY VANTAGE POINTS — FEASIBLE through the ASI. The native surface
	    exposes coordinate/volume fog reveal, whole-map reveal, and map-discovery
	    controls. Define persistent regional tower states and map markers, suppress
	    or repeatedly counter normal travel reveal, then reveal the intended volume
	    at each vantage point. Test existing saves, restart persistence, boundaries,
	    interiors, mission reveals, and whether already revealed fog can be reset.
		
	50. DEATH BLOODSTAIN / LOST MONEY — outside missions, death now replaces any
	    previous stain with a navmesh/ground-corrected marker containing the lost
	    cash. Touching it restores the money; a second death destroys the old stain.
	    State persists in GameplayTweaks.bloodstain.dat. Completed Gambler ranks
	    protect 10% each, so Rank 0 drops 100% and Rank 10 drops nothing. Test map
	    marker, restart persistence, second-death loss, mission suppression, terrain
	    correction, and several Gambler ranks. The current retest build adds the
	    always-on radar-edge modifier and renders a dark-red ground pool plus a
	    narrow pulsing red beam; pickup radius is reduced so the marker remains
	    visible before collection.

	71. EXISTING-SAVE COMPATIBILITY WARNING — persist whether a save began with
	    the overhaul active. On every load of a save begun without it, show a
	    blocking acknowledgement warning that progression or balance may be
	    invalid and recommend starting a new game.

	72. TIER-I HORSE STAMINA TONIC — add the missing basic horse-stamina tonic as
	    a normal catalog item, using existing bottle/icon assets where possible;
	    identify and create only the genuinely missing asset/data records.

	79. VISIBLE GOLD OVERFILL — render fortified cores and bars as a second golden
	    overlay whose length shows the remaining overfill, BOTW-style, instead of
	    reducing fortification to a binary golden state.
	    FEASIBILITY (Fable): reading the overfill amount is solved -
	    GET_ATTRIBUTE_BONUS_RANK returns the fortified portion per core. Drawing
	    is the open question: no native exposes the core ring's screen geometry.
	    Lexer's constraint approach makes it viable though - require specific
	    static HUD settings + extended minimap so the cores sit at a fixed spot,
	    detect the resolution, and compute ring positions from that (RDR2 has one
	    HUD scale and no real safezone slider to fight). Remaining risk is
	    matching the ring's arc geometry precisely and that the cores animate/hide.
	    Verdict: feasible with a fixed-HUD requirement; moderate effort; the arc
	    overlay is the finicky part. Not blocked.

	82. NO SURRENDER TO THE LAW / PAY OFF BOUNTY ON THE SPOT -- If you have a serious
	    crime on your record (High severity) you cannot surrender to bounty hunters
	    nor police. INSTEAD of surrendering, offer to PAY OFF THE BOUNTY THERE AND
	    THEN, provided the player actually has the money: show the amount owed, take
	    the cash, clear the bounty and call off the pursuit. If they cannot afford it
	    the option is unavailable (or greyed out with the shortfall shown) and the
	    fight/chase continues. Needs: read the current bounty per region, a prompt
	    during a law/bounty-hunter encounter, cash deduction, and clearing wanted
	    state. Doable?

	23. REDUCE NON-LOOT PAYOUTS — consider lowering mission/activity/scripted
	    cash rewards so the economy cannot be bypassed by oversized payouts.
	    Reference: Less Money - Economy Reworked (Nexus 1256); crack it open to
	    identify which payout sources are data versus script-controlled.

	Does this just affect some story mode payouts or anything else? Oh, also, make sure it doesn't conflict with the banking mod by taxing transactions. THe reference version on nexus should already be designed with that in mind?

	6.  SKIP STARTUP MOVIES — no Rockstar logos / game intro at launch.
	    Blocked: the movies are .bik files; replacing them needs the proprietary
	    Bink encoder. Boot config (startup.ymt) does NOT reference them (verified).
	    Unblock: obtain a Bink encoder, or drop.

	8.  FAINTER LOOTED MARKERS — the X (looted body) and paw (skinned animal)
	    minimap markers become more transparent.
	    Blocked: no blip-alpha native; needs the blip/sprite config dug out of the
	    archives in an OpenIV session (game closed).

	22. REMOVE AUTOMATIC AMMO PICKUP — removes TAKE_AMMO QuickBehavior entries
	    from lootconfigdata.meta and is installed as lml/LexNoAutoAmmo. This file
	    controls looting prompt/quick-behavior rules; it is not yet exposed in a
	    dedicated editor control. Needs in-game confirmation after restart.
	
	What are looting prompt/quick behavior rules? Why aren't they in the editor? Shouldn't they be? Why is this a seperate mod -- shouldn't we add this to our existing mod, either by adding the ability to make it through the editor or by simply doing a one-off change to the data side of our mod? ~ Lex

	27X. DS3-STYLE OVERFLOW STORAGE — implement an ASI-owned persistent reserve for
	    acquisitions beyond the player's active capacity. Raise relevant engine
	    caps enough that ordinary world pickups, corpse loot, shop purchases,
	    crafting outputs, and rewards are accepted first; observe the granted
	    quantity, keep only what fits the mod capacity, and move the remainder into
	    storage. Audit every acquisition path and suppress/repair duplicate pickup
	    notices, challenge/stat increments, and item-use side effects. Do not call
	    this universal until rejected-at-cap loot and forced mission grants pass
	    in-game tests.

	12. Remove all base-game HP/Stam/Deadeye XP gain. All of it. These should only increase through challenges.

	93. PARTIAL BOUNTY PAYMENTS — CLAUDE HANDOFF; FAILED IN-GAME TWICE
	    2026-07-28. Screenshot evidence: the real Post Office bounty screen was
	    open with Lemoyne/West Elizabeth/New Hanover each $300, cash $6.25, and
	    no partial-pay prompt. The simultaneous log was:
	    `shop_post_office=0 shop_controller=0 bounty=30000 cash=625 matches=0
	    state=-1 available=0 ledger=6,0,0,0,0,0`. Therefore both presumed script
	    gates are false in the actual UI, and the assumed six-slot ledger mapping
	    does not mirror the three visible $300 bounties. Discard those assumptions.
	    Identify the real active script/UIApp/databinding state from decompiled SP
	    scripts and inspect the actual per-state bounty storage/update path used by
	    the vanilla PAY action. Integrate into the existing screen if possible;
	    otherwise create a prompt that is gated by proven menu state, not guessed
	    script names. Intended transaction pays `min(cash, selected/current
	    regional bounty)`. Prove selected region, partial/full payoff, HUD/map/
	    menu agreement, all states, persistence, and insufficient cash.

	    2026-08-03 ROOT TRACE: `shop_post_office.c` creates the actual rows under
	    `GenericShop/ItemListEntries/{Ambarino,New Hanover,Lemoyne,West
	    Elizabeth,New Austin,Guarma}`. Each row stores template `-698448975`,
	    `uiItemID`, `price`, and `itemEnabled`; vanilla deliberately greys the Pay
	    action when cash is below the full row price. Selection is
	    `GenericShop.ItemListEntryIndex`. The failed ASI passed nested slash paths
	    to a native that only retrieves root containers, so it found zero rows and
	    changed nothing. Rockstar exposes the real UI item list at
	    `Global_1914319.f_16855.f_31`; the installed build now retrieves row
	    contexts from that list, enables bounty rows when partial payment is
	    possible, pays `min(cash,bounty)`, writes the remainder to
	    `Global_40.f_358[state]`, and refreshes the live row. UI integration and
	    persistence remain unconfirmed until the next full-restart test.

	42. ONE CARRIED MASK ON THE REGULAR ITEM WHEEL — CLAUDE HANDOFF; FAILED
	    IN-GAME TWICE 2026-07-28.
	    The disable-only version left generic `KIT_BANDANA` on the item wheel and
	    greyed the real horse-wheel masks. Do NOT add a parallel F6 selector:
	    the wardrobe already lets the player equip exactly one mask, and that
	    equipped wardrobe mask must automatically become the carried mask. Find
	    the actual equipped outfit/component state used by wardrobe/bandana
	    scripts and mirror that mask into the ordinary item-wheel bandana slot
	    with its real icon and full-mask toggle behavior. Remove the horse-wheel
	    mask selector without merely disabling/greying its entries. Prove changing
	    masks through the normal wardrobe updates the carried item automatically.

	    ROOT PIPELINE TRACE: `docs/INVENTORY_RADIAL_ARCHITECTURE.md`.
	    `quickselectitems.ymt` is the missing item-to-slot layer:
	    `KIT_BANDANA` maps to `CLOTHING_ITEMS`, while Story masks map to
	    `HORSE_LARGE_MASKS`. `short_update` separately enumerates the ordinary
	    bandana and large-mask catalog categories and calls inventory item
	    enable/disable; those natives do not add/remove HUD collection members.
	    The earlier catalog-only, GUID-move, hide/disable, and guessed
	    HUD-collection implementations are rejected.
	    INSTALLED 2026-07-30: `MyOverhaul/quickselectitems.ymt` removes the real
	    bandana and all ten Story mask mappings, gives ten custom carrier items
	    the ordinary `CLOTHING_ITEMS` mapping, and leaves no Story item assigned
	    to `HORSE_LARGE_MASKS`. The ASI keeps exactly one carrier in inventory:
	    the persisted/wardrobe-observed mask, or a bandana fallback during
	    missions. Carrier use redirects into Rockstar's real mask/bandana
	    interaction states. The 2026-07-30 live pass proved both
	    `quickselectitems.ymt` and `catalog_sp.ymt` loaded, but also caught
	    `LEX_CARRIED_MASK_PSYCHO present=0 changed=0`: the first ASI incorrectly
	    tried to grant a CLOTHING record through `SLOTID_SATCHEL`. The next
	    staged logs exposed the deeper ABI error: `InventoryGuid` was only 16
	    bytes, but Rockstar `struct<4>` GUIDs are four 64-bit `Any` values (32
	    bytes). The 2026-08-03 live pass then proved the correct carrier was present
	    and followed wardrobe selection, but the radial stayed blank. The remaining
	    cause was availability: `short_update` performs its enable pass before the
	    runtime carrier is granted. The installed build now explicitly enables the
	    present carrier after each sync. Full-restart in-game acceptance is still
	    required.

	112. VISIBLE, DODGEABLE SLOW PROJECTILES — Lexer confirmed in-game
	    2026-07-29 that the installed firearm bullets are definitely slower.
	    `CWeaponInfo.Speed` therefore does control useful projectile travel and
	    no further hitscan/velocity-path investigation is required. The remaining
	    player-facing problem is visibility: add convincing tracers, streaks, or
	    another per-shot flight effect to hostile and player firearm projectiles
	    so their direction and travel can actually be read and incoming fire can
	    be dodged. The existing `[ProjectileVisibility]` marker only approximates
	    the player's firing ray and defaults off; it is not accepted as hostile
	    projectile tracking. Keep `[ProjectileSpeed] GlobalFirearmSpeed`
	    automatic with no hidden PowerShell step, preserve impact/damage behavior,
	    and verify visibility from both ends across daylight, darkness, weather,
	    multiple simultaneous shooters, shotguns, and ordinary engagement ranges.
	    Per-cartridge design/tooling remains #188.

	    2026-07-30 FOLLOW-UP: `[ProjectileVisibility]` now defaults on and creates
	    a five-point luminous moving streak for each player shot and each nearby
	    ped actively fighting the player. Enemy streaks originate at the firing
	    hand/muzzle area, travel toward the player at `GlobalFirearmSpeed`, and
	    expire after passing the target; player streaks follow the camera firing
	    direction. This is synchronized visual flight, not a damage replacement.
	    Muzzle alignment, cadence, shotgun presentation, and real impact endpoint
	    still require in-game confirmation.

	</Class_A>
	
	<Class_B>
		189. CUSTOM GAMEPLAY CAMERA CALIBRATION AND TWO-STATE VIEW TOGGLE — add an
		in-game calibration mode whose hotkeys move the gameplay-camera offset on
		exact X/Y/Z axes, preview/revert it, and save the chosen values as the
		shipped defaults/configuration used by all mod users. Support distinct
		left/right-shoulder profiles for standing, crouched, and prone stances
		(or prove that mirroring one shoulder offset is equivalent). Disable the
		two intermediate third-person zoom levels so V toggles only the configured
		third-person view and first person. Preserve aiming, cover, horseback,
		vehicles, cutscenes, missions, scopes/binoculars, and other scripted
		cameras; forward prone framing must keep Arthur visible. First determine
		whether native stance/shoulder offsets can be overridden safely or require
		a replacement scripted gameplay camera.

		176. ALLIGATOR SKINNING MATRIX IDENTIFICATION — identify which of the three
		alligator archetypes represents each physical size/variant from vanilla
		model, ped, and loot references, then rebuild their matrix yields without
		guessing or collapsing distinct animals.

		180. REVOLVER-RELOAD GLINT AUDIT — trace the six synchronized reload glints
		to their particle, shader, animation, or script source and determine which
		size, brightness, fade, timing, synchronization, and randomness parameters
		are actually editable before choosing the visual rework.

		140. BUTCHERY AND DECAY REWORK — make skinned carcasses unsellable after
		their useful meat and parts are harvested, and implement continuous
		quality/value decay from Perfect to Good to Poor to worthless. Finalize
		whether skinning itself butchers or a separate Butcher's Knife interaction
		does so, then expose the intact carcass's time-decaying sale value.

		145. ALCOHOL CONSUMABLE EFFECTS (numeric strength) — the real per-item alcohol
		values (0.10-0.50 on the official 0-1 inebriation scale; Sober 0-0.49, Drunk
		0.50-0.74, Wasted 0.75-0.99, Blackout 1) are NOT in catalog_sp.ymt (grep = 0
		hits) and are NOT determined by the drink-class tag (Moonshine 0.30 and Gin
		0.17 share the identical tag 0xEFAD85F3). They live in the game's drinking/
		consumable-effect data, which is not yet in this project. Work: locate that
		data source, bring it into the project, and expose the numeric alcohol value
		per drink item in LEXEDITOR as a real editable field (the current "Drink
		class" selector is only the coarse class tag, not the value). Then allow
		editing intoxication strength per drink.
		
		- If I don't get this working -- moonshine instant ko, specifically -- then the "pass out to guarma" exploit might not work due to decreased carry limits, which could be extra bad b/c i want that one challenge implemented that relies on it



		143. EFFECT DURATION-CATEGORY EXPERIMENT — concoct and run a controlled
		in-game test to determine what `durationcategory` actually controls for
		persistent catalog effects. Create deliberately contradictory test records
		that vary Behavior ID, `time`, `timeunits`, and `durationcategory`, then
		measure duration, stacking, replacement, UI/radial tier behavior, save/load
		persistence, and whether categories 1-4 have behavior beyond labels. Record
		confirmed rules in AGENTS.md and expose the findings in LEXEDITOR help.
	
		174. ANIMAL TRACK GENERATION AND TRACK-LED HUNTING — determine whether tracks
		are generated only by live animals, persisted from recently streamed
		animals, or placed independently by scenarios/data. Trace the Eagle Eye,
		tracking, spoor, and ambient-animal spawn paths in vanilla scripts/data and
		a controlled in-game sample. If tracks can exist independently, design a
		hunting model with near-zero incidental animal density but substantially
		more discoverable tracks, so finding animals usually begins by deliberately
		locating and following sign rather than encountering wildlife at random.
		171. ENEMY REWORK — redesign enemy stats, hp, weapon and ammunition loadouts so
		enemy archetypes, gangs, regions, and difficulty tiers have distinct,
		believable combat roles instead of generic distributions. Inspect Realistic
		Loadouts as research/reference, then recreate the mechanism from
		vanilla data and scripts without shipping its files or wholesale values:
		https://www.nexusmods.com/reddeadredemption2/mods/1371?tab=description
		Should probably be like a new Mobs tab with Humans and animals subtabs. both let me edit whatever stuff is common to both -- stats and shit? the humans one lets me edit loadouts and whatever. plus whatever relevant stuff i might have missed?

		148. HORSE FEED-BOND: FIND THE REAL DATA SOURCE — Lexer cannot find any
		bond-related tag on CONSUMABLE_SUGARCUBE, so feed-bond is NOT a simple catalog
		tag. Confirmed NOT it: 0x054FF04E is a broad "edible" tag shared by 49 items
		(herbs, jerky, candy, corn, oat cakes...). The old scripted sugar-cube watcher
		was REMOVED 2026-07-24 — it polled the inventory every 250ms and added
		PA_BONDING on top of the game's own native grant, i.e. double-counting.
		WORK: find where the game actually decides "this item can be fed to a horse and
		grants N bond". Look at the item's effects/effectids rather than tags, the
		horse/compendium data, and grep the decompiled scripts
		(_downloads/RDR2-Decompiled-Scripts/script_rel/) for the feeding/bonding
		routines. Bonding is ranks 0-4 with model/data-defined thresholds, not one
		universal percentage scale. GOAL: expose it in LEXEDITOR so feed-bond can be
		added to ANY item with a chosen value — data-driven, not scripted.
		
		173. PHANTOM TRAIN MARKERS — fix train tracking so a marker is created and
		retained only while it is backed by a confirmed live train entity. Retire
		stale markers promptly after despawn, mission cleanup, streaming loss, or
		fast travel, and reacquire only from a real train rather than a cached route
		or timetable position. Reproduce the failure seen in the existing train
		marker mod and test moving, stopped, mission, despawned, and streamed-out
		trains.
	138. ARTHUR'S SICKNESS REWORK — make tuberculosis meaningfully affect the
	    overhaul's survival systems instead of remaining mostly cosmetic. Design
	    and implement illness stages that increase Health, Stamina, and/or Dead Eye
	    Core drain, reduce sleep recovery, or otherwise worsen upkeep as Arthur's
	    condition progresses. Identify the game's reliable sickness-stage state,
	    expose configurable stage multipliers in the mod INI/editor, and avoid
	    applying the penalties before the story has actually made Arthur ill.

	96. SEPARATE TRINKETS VIEW — A trinket-only inventory view is FEASIBLE, but a
	    new tab inside Rockstar's existing satchel is not a data-only change. The
	    decompiled satchel UI builds fixed databinding containers and hardcodes
	    trinket/talisman handling. Implement either a runtime datastore/UI hook that
	    adds a native-looking category or an ASI-owned inventory page; item filtering
	    is straightforward, while seamless insertion into the vanilla tab bar is
	    the unproven part.
	98. HOLSTER KEY ALWAYS HOLSTERS — Putting away your weapon (hitting tab) should always put away your weapon. Sometimes Arthur just...keeps running, repeater in hand, just in a different pose? I really hate it. Anyways, you can get the exact effect I WANT by just swapping to fists.


	66. PREMIUM-CIGARETTE CARD DROPS — built in GameplayTweaks.asi and staged in
	    the disabled Story stack. The vanilla card granted by acquiring a Premium
	    Cigarette pack is removed; loose cigarette cards found in the world remain
	    normally collectible, and preexisting cards are preserved. The ASI
	    identifies an actual Premium Cigarette item-interaction plus inventory
	    consumption, then rolls 20% per cigarette and grants a random unowned card;
	    after all 144 are owned it permits random duplicates. Test after restoring
	    Story mods and restarting: buy/pick up a pack (no card granted), collect a
	    loose card (card retained), discard cigarettes (no roll), smoke many
	    cigarettes (roughly 20% awards), and confirm awarded cards persist and use
	    the normal acquisition notification. Confirm stranger-mission and set
	    turn-in progression still recognizes the awarded cards.

	-- Wait, doesn't the pack itself just give you the seperate cigarettes item? I want to locate them, make sure they're seperately and properly labelled in the editor, then make consuming the actual cigarette the thing that procs it.

	78. REMOVE FREE-ROAM SPEED LIMITS — remove arbitrary settlement/region speed
	    caps outside missions while preserving mission-scripted limits.
	    References: Nexus 5258 and Nexus 975.

	81. BOUNTY-HUNTER SYSTEM EDITOR — identify and expose spawn rate, group size,
	    animal/allied support, equipment, tactics, escalation, and other tunable
	    bounty-hunter behavior so encounters become deliberate challenges rather
	    than recurring annoyance.

	67. RDO-STYLE FAST CORPSE LOOTING — replace or accelerate Story Mode's slow
	    human-corpse search with the short Red Dead Online-style loot interaction,
	    without globally speeding skinning, gathering, crafting, carrying, or
	    unrelated interaction animations. First compare SP/MP loot animation sets
	    and `lootconfigdata.meta` rate selectors, then import/repoint only the
	    required vanilla-mounted RDO clip or apply the narrow rate override. Verify
	    standing, crouched, moving, obstructed, combat, mission, and interrupted
	    looting; preserve item transfer, prompts, body marking, and cancellation.
	    Reference only: Just Get The Loot Already (ImABotBeepBoop), which proves
	    loot animation speed/rate changes are data-feasible but modifies a much
	    broader set of interactions than wanted here.
    
	    Make it so you can just set which one is used -- fast or slow -- so when I design the mechanic  that unlocks fast looting you can implement it real quick. ~Lex

	24. FISTS KNOCK OUT, NEVER KILL — ordinary punches should render NPCs
	    unconscious rather than dead. Research knockout thresholds, recovery,
	    kicking/stomping, melee damage and mission compatibility. Reference:
	    Rededrunk's Ultimate Combat Overhaul (Nexus 5731). Initial mechanism found:
	    damages.meta adds DRA_KNOCKOUT to light/heavy/combo/haymaker actions and
	    lowers unarmed damage; pedhealth.meta defines per-health-profile
	    KnockedOutHealthThreshold/ToRecover/Count. UCO also uses an ASI, so verify
	    whether it enforces nonlethality or handles recovery/crowds at runtime.
	
	I'm surprised fists didn't knock out to begin with. Then how DID you knock out in vanilla? Anyway, just tell me what fields to edit in the Weapons tab under Unarmed and I'll do it myself. ~Lex

	51. RECOVERABLE UNIQUE WEAPONS — unique hatchets, tomahawks, and every other
	    one-off weapon that can be permanently lost after being thrown or dropped
	    must remain recoverable. Inventory all loseable uniques, track them after
	    first acquisition, and return a missing unique to the weapon locker after
	    its world projectile/pickup despawns or unloads. Never duplicate a weapon
	    that still exists in inventory, on the horse, in the locker, or as a live
	    world pickup; preserve ordinary manual retrieval and mission behavior.

	57. SELL DUPLICATE CIGARETTE CARDS ONLY AFTER SET TURN-IN — keep every card
	    unsellable until its twelve-card set has been completed and mailed to
	    Phineas T. Ramsbottom; after that set's turn-in, duplicate cards from that
	    set may be sold. Track the twelve independent set-completion states and
	    apply resale eligibility without making the submitted originals reappear.
	</Class_B>
	
	<Class_C>
		188. PER-CARTRIDGE PROJECTILE-SPEED TOOLING AND BALANCE — extend #112's
		global firearm-speed build setting into cartridge-aware tooling. Map every
		weapon/damage-mode to its actual ammunition family, expose editable speeds
		per cartridge (including caliber, regular/express/high-velocity/split-point,
		+P/high-pressure, explosive, shotgun loads, arrows and special rounds),
		then design and set physically and gameplay-coherent defaults. Verify that
		one weapon supporting several cartridges uses the selected cartridge's
		speed; if `CWeaponInfo.Speed` is only per weapon, build the safe runtime
		switch/patch layer required instead of falsely presenting per-cartridge
		values. Preserve the complete 11-file Rockstar weapon stack and provide
		LEXEDITOR comparison/validation tools before balancing wholesale values.

		181. GUNSLINGER-QUEST MAP REVEAL — when “The Noblest of Men, and a Woman”
		begins, invoke the same Story-script path that reveals all four gunslinger
		locations after inspecting their photographs, without requiring the player
		to examine each picture.

		109. CASING SPAWN POSITION AND MOMENTUM TUNING — temporarily restore
		vanilla casing visuals for comparison, tune custom casing spawn position
		and inherited/ejection momentum to match, then remove the reference behavior.

		136! REMAINING ITEM ICONS — ~15% of items still show '?' in LEXEDITOR
		(item_textures ammo-ad images, gun swatches, etc.). femga does not host
		these dictionaries and the game archives store them under hashed paths in
		packed .ytd texture dictionaries, so the scripted extractor cannot target
		them. The straightforward path is OpenIV (needs computer control): browse
		the ui texture .ytd files, export the missing dicts as PNGs into
		editor/assets/, and extend inventoryIconUrl to serve them locally. The
		animal-product bulk (SATCHEL_TEXTURES) already renders via femga.
	
		162. BAIT: FIGURE OUT HOW IT ACTUALLY WORKS, THEN MAKE IT USEFUL — determine the
		real mechanics of herbivore/predator/potent bait (spawn chance, radius,
		duration, which species respond, whether it affects quality or only spawns,
		interaction with cover scent and wind). Bait is currently near-useless in
		practice. Once the mechanics are known, retune so it is a genuine hunting
		tool. Investigate the bait items' effects and any related data/natives.

		161. IDENTIFY THE STEW / REGIONAL FOOD ITEMS — the catalog has many overlapping
		stews (plain beef stew, regional stews, differing quality levels) and it is
		unknown which ones actually appear in game or where. Method: temporarily give
		each candidate item a distinct effect that shows a different on-eat message
		box, then identify them empirically as they are encountered/bought. Then
		document which are real, which are cut/unused, and fold the findings into
		descriptions and shop stock.
		
		165. EMPTY BOTTLE NONLETHAL THROWABLE — make the Empty Bottle a throwable
		inventory item whose impact can stagger or distract but cannot kill. Reuse a
		real throwable/projectile path rather than a cosmetic prop; decide whether
		it survives impact or breaks, and integrate it with the empty-bottle
		collection work in #103.

		164. UNIQUE DESCRIPTIONS FOR EVERY PLAYER-FACING ITEM — author concise,
		distinctive descriptions for every item the player can actually encounter,
		following docs/DESCRIPTION_WRITING.md. Preserve all user-authored text and
		every `Deprecated.` record exactly unless Lexer directs a replacement.
		Internal helpers, containers, components, and records with no player-facing
		surface must be identified rather than given fabricated flavor text.
			
		155. BINOCULARS: TRUE INSTANT ENTRY (STILL NOT SOLVED) — Lexer has asked many
		times to be put straight into the binocular view with no visible pull-out.
		FAILED APPROACHES, do not repeat: (a) hiding the weapon model with
		SET_PED_CURRENT_WEAPON_VISIBLE — hides the binoculars themselves; (b)
		per-frame CLEAR_PED_SECONDARY_TASK — cancels the binocular scope task and
		makes the view flick in/out/in; (c) the binocular scaleform natives
		0x21F00E08CBB5F37B / 0x5AC6E0FA028369DE — overlay ONLY, does not change camera
		or FOV, so the glitched model is still visible behind it.
		STILL UNTRIED: driving the binocular CAMERA directly (scripted cam / FOV) so
		the player is in the looking-through state independent of the weapon draw;
		and the SET_CURRENT_PED_WEAPON trailing flags (now exposed as
		[Binoculars] EquipP3/P4/P5 for live testing).
		NOTE the keyboard-specific model displacement is caused by F = INPUT_PICKUP;
		default key changed to B, which should remove that symptom on keyboard.

		153. BINOCULAR ZOOM LEVELS — expose and retune the binocular zoom. Find where the
		zoom steps/FOV limits for WEAPON_KIT_BINOCULARS (and _IMPROVED) are defined
		(scope/weapon component data or the camera FOV the scaleform view uses), then
		make the levels editable — ideally ini-tunable in [Binoculars] (min/max FOV or
		a zoom-step list) so the regular and improved binos can differ meaningfully.
		
		And while we're at it le's try and make the bino overlay a bit less oppressive. ~Lex
		
		156. POISON ARROW KILLS YIELD NO MEAT — animals killed with poison arrows drop no
		meat, so they are good for clean pelts but useless for food. Verify this is
		vanilla behaviour, then decide: keep as an intentional trade-off (document it
		in FEATURES/descriptions so players know), or change it so poisoned kills
		still yield meat. Lexer to decide direction.
		
		152. BINOCULAR PROMPTS + PHOTOGRAPH FROM BINOS — while in binocular view, fix the
		corner button prompts: REMOVE "Put away", ADD "Use camera" bound to MMB on
		keyboard and R3 on gamepad, which swaps to the camera. BETTER GOAL: skip the
		swap entirely and let the player photograph directly from binocular view
		(click to take the photo without leaving binos). Investigate the binocular
		scaleform natives found 2026-07-24: GRAPHICS::_0x21F00E08CBB5F37B(component)
		"COMPONENT_BINOCULARS_SCOPE01" triggers the binocular scaleform and
		GRAPHICS::_0x5AC6E0FA028369DE() closes it — the prompt strip is likely part of
		that scaleform, and driving it directly may allow custom prompts and a
		photograph action without a weapon swap.
	104. MISCELLANEOUS ROCKSTAR BUGFIXES — audit longstanding single-player bugs
	    Rockstar never fixed, determine which can be repaired safely through data
	    or ASI hooks, and implement a compatible bugfix collection. Consider
	    releasing this as a separate modular bugfix mod so players can use it
	    without the overhaul. Candidate mods to inspect as research/reference:
	    https://www.nexusmods.com/reddeadredemption2/mods/4909
	    https://www.nexusmods.com/reddeadredemption2/mods/1425
	    https://www.nexusmods.com/reddeadredemption2/mods/1197
	    https://www.nexusmods.com/reddeadredemption2/mods/704
	    https://www.nexusmods.com/reddeadredemption2/mods/2953
	    https://www.nexusmods.com/reddeadredemption2/mods/9006

	77. PLAYER-PAGE CORE-DRAIN DISPLAY — identify what drives the three displayed
	    core-drain rates, determine whether ASI-controlled rates can be reflected,
	    and either show the overhaul's real values or allow the misleading display
	    to be hidden.

	80. HONOR ACTION EDITOR — audit bounty-hunter and bounty-dog honor behavior,
	    fix any inconsistency, and add an Honor editor surface listing known honor
	    gain/loss actions with editable amounts and disable toggles.

	90. CASING CUSTOM PICKUP SOUND — replace the placeholder SELECT frontend
	    click with a dedicated brass-pickup sound. Requires audio-bank
	    modding research (custom sound assets, not just soundset names);
	    surface the sound fields in LEXEDITOR's settings tab meanwhile.

	45. REMOVE WORLD-COLLECTIBLE MASKS — remove or suppress the fixed world pickups
	    for every mask reassigned to Bandit challenge rewards, so those masks cannot
	    be collected early and challenge completion is their only acquisition path.
	    Preserve masks not used by the challenge rework and existing-save ownership.

	48. ANCIENT TOMAHAWK REWORK — in vanilla I think that throwing it and not recollecting it just makes it so you lose it forever, like many other unique weapons. this weapon, however, should return to your inventory after being thrown.

	53. REMOVE HUNTER-HATCHET WORLD PLACEMENTS — remove the fixed world pickups
	    for both WEAPON_MELEE_HATCHET_HUNTER and
	    WEAPON_MELEE_HATCHET_HUNTER_RUSTED. One has been pruned from progression;
	    the other is intended to be a powerful unlock rather than free world loot.
	
	Prob shouldn't be taking shit out until I Confirm it's not in the compendium first. Is it? ~ LEx.

	52. HUNTER'S HATCHET REWORK — make the Hunter's Hatchet instantly kill any
	    animal without reducing carcass/pelt quality, matching the saved in-game
	    description. Detect a valid hit/kill by this exact unique weapon, preserve
	    legendary/scripted animal behavior, and award Perfect-quality yields
	    without duplicating carcass or skinning loot.

	</Class_C>
	
</Actionable>

<Waiting_on_Lexer>
	13. NO SPARKLE ON OWNED GEAR — GameplayTweaks now enumerates live pickups and
	    suppresses their highlight/light when the pickup's catalog model maps to a
	    weapon the player already owns. The generated from-scratch map covers 80
	    weapon models. The game's hats are not CPickupData entries and their catalog
	    records deliberately contain blank model fields, so the same mechanism
	    cannot identify them. Waiting on one safe Story-mode sampling session nea
	    a collectible hat to capture its live object/metaped identity and finish the
	    separate hat path.

187. UFCO CLIMBING-CHEST REVIEW — temporarily disable GameplayTweaks climbing
    and restore the backed-up `UFCO.asi`/`UFCO.ini` solely for Lexer to visit
    all nine town chests and five wilderness gold chests. Record exact
    coordinates, container models, loot contents/quantities, respawn behavior,
    and whether each location is actually enjoyable to reach. Remove UFCO again
    afterward, then decide whether the overhaul should add a smaller set of
    original climbing-reward chests with its own locations and balanced loot.

183. MULTI-VARIANT ANIMAL REVIEW — Lexer will decide how the editor/mod should
    treat these himself: Alligator `_01/_02/_03` (large adult, standard adult,
    small/carryable); Turkey `_01/_02` (standard model/carcass variants, with
    Rio Grande separate); Woodpecker `_01/_02` (Red-bellied and Pileated,
    numeric mapping not explicitly labelled); Wolf base/`_MEDIUM`/`_SMALL`
    (physical/carcass size variants that may also carry outfit/species meaning).

184. FISH MODEL-SIZE VARIANT REVIEW — Lexer will decide how the editor/mod
    should treat these himself: Bluegill MS/SM; Bullhead Catfish MS/SM; Chain
    Pickerel MS/SM; Channel Catfish LG; Lake Sturgeon LG; Largemouth Bass
    LG/MS; Longnose Gar LG; Muskie LG/ML; Northern Pike LG; Perch MS/SM;
    Rainbow/Steelhead Trout LG/MS; Redfin Pickerel MS/SM; Rock Bass MS/SM;
    Smallmouth Bass LG/MS; Sockeye Salmon LG/MS. Suffixes are physical model
    buckets: SM small, MS medium-small, ML medium-large, LG large—not quality
    tiers or separate species.

-- i'd prefer it if, maybe, you had to craft animal meat containing recipes straight from the carcass. otherwise you can just hoard tons of raw meat in your satchel. then again this would also make a lot of the more complex ones impossible to make , so who knows...
-- actually i basically need to figure out what i want cooking to do, what i want to craft, what recipes, then i'll know what meat types i want and how to get them. ask bots for various meat based meals or things to craft. oh, this will require eggs, which will require re-adding items from online.
- https://reddead.fandom.com/wiki/Bird_Eggs BRING BACK EGGS
-- create some sort of poison meat/toxic meat item. maybe for harvesting rotted carcasses, but for the poisoned animals you can find in that one part of the game as well as vulture meat.
-- rename bird feathers...recontextualize somehow...to explain why you can kill a bird and only get 1...maybe make it tailfeathers. still too many? Long tailfeather? idk. ask the bot. regardless this is one we definitely want to put in the script/explanatinos/features because wow is it ever an insane one in the original game. and the devs didn't even think to change some text to try and explain it...
-- maybe we'll end up doing the opposite: once i get the custom crafting menu, we can deprecate the generic flight feather and make all feather-using recipes craftable with any type of feather. in fact, that's what we're going to do right now because i removed both recipes that currently use the flight feather
-- abolish eagle eye: constantly toggling that shit sucks bruh. trails and plants should be highlighted naturally. perhaps even with an upgradeable radius?
160. DINER / RESTAURANT MENU WORDING FOR FOOD DESCRIPTIONS — visit the game's
    diners and restaurants and read their in-world menus; reuse that authentic
    period wording (dish names, phrasing) for our food item descriptions. Needs
    Lexer to visit them in game (or a source of the menu textures/text).
	-- Fast walk: there's a fast walk mod. How to work in its functionality? 4th move mode? Replace walking? IDK
	https://www.nexusmods.com/reddeadredemption2/mods/1173
- Saloon whiskey shot. Needs a reason to exist.
106. DEPRECATED ITEM REVIEW — Check out all the items I've deprecated. Consider precating them.
	-- Reimplement herbal meat types.
	-- Reimplement golden cores and bars.
107. UNIQUE WEAPON REWORK — Rework all unique weapons.
-- Guarma rework: look at some mods that let you freely travel back and forth diagetically.
-- Design explorer tree: #7 still empty, fuck
-- Implement explorer tree: requires #7 to be thought up. also "glitch to guarma" challenge requires a way back home from guarma, requires guarma rework.
119. RESTRICT HOLD-TO-REST — Remove the hold E to rest ability unless you have empty cores? Especially annoying because every time I try to hold E to collect a casing it comes up right after. It'll be necessary as a fallback if players run out of resources, so they don't die over and over due to starving. Wait, I need to set the maluses for empty/near-empty cores, anyway.
92. EXPLORER CHALLENGE TREE AND GOLDEN TICKET FAST TRAVEL — Implement my Explorer tree. Should be self-explanatory? Upon entering the CHallenge 10 Marker:
"Travel to the marked point in Coulter, on foot, in under a day, without killing, dying, or consuming anything. Also, an invincible bear will be chasing you at all times. Have fun!"
Upon winning, you earn the Golden Ticket trinket. When you have it, it just unlocks the vanilla "Fast travel" option you get at campsites, but when you use it it opens up your world map where the only icons are the campfire ones and you select one and it takes you there.
125. GAMBLING CHALLENGE REWORK — Gambling challenges rework: (requires partial bounties  and wallet size)
ORder of challenges 1-9 set randomly on new game so each playthrough has a different order. Completing each challenge increases your wallet size 1 rank and reduces cash dropped on death by 5% and gives you a popup saying so with the new values. I shoudl be able to set these values in the ini at any time.
Wallet sizes:
	0. $1.00
	1. $2.00
	2. $4.00
	3. $7.50
	4. $12.50
	5. $20.00
	6. $40.00
	7. $75.00
	8. $150.00
	9. $250.00
10. Unlimited
Challenge 10: Upon walking into the marker
You have been poisoned. Using any healing item or dying will end the challenge. You are to win a game of Dominoes in X, Five Finger Fillet in Y, Blackjack in Z, and Poker in A. Don't worry, it won't cost you a thing -- you will be gambling with your life. (Bets placed with health. Lose, lose HP. Win, get health back. Maybe time stays stopped when you're gambling in RDR2? If so, must remove this. But for best effect, take a look at my poison effect rework and ensure the health drain rate is in HP lost per REAL TIME SECONDS.
Winning earns you the gold TODO think of this one
-- animal fat. make uses. make sources.



weapon master: kill w/ poison weapon


hunter: kill a bear without guns






30. DYNAMITE EXPLOSION RETUNE — expose and adjust dynamite/volatile-dynamite
    explosion radius, damage/power, impulse, and camera shake. Weapon records
    select EXP_TAG_DYNAMITE; trace the explosion-tag tuning before editing.
	
	Actually, why don't we just figure out what effects on the dynamite item(s) control the explosion power and name them, then I can tune them myself in the editor? ~ Lex

172. LOW DEAD EYE / EAGLE EYE INTERACTION — low or empty Dead Eye currently
    disables Eagle Eye as a side effect. Decide whether Eagle Eye should remain
    independently available (bugfix) or actively consume the outer Dead Eye bar
    while in use; then implement the chosen rule without spending the core as a
    reserve or breaking tracking/tutorial sequences.

84. PRESERVE BANKING MOD FOR LATER MERGE — Banking the Old American Art is
    preserved read-only at datasets/banking/ (gitignored like the other
    reference mods; NOT committed, per the repo's own never-commit-reference
    policy). Its Banking.ini already implements features that overlap our own
    TODOs: lose-money-on-death with a configurable PERCENT_OF_MONEY_LOST, a
    saddlebag money-bag mechanic, a MONEY_LIMIT wallet cap, and an Armadillo
    bank toggle — useful reference for #94 (wallet size) and #50 (death money
    loss). Actionable = recreate the banking economy from scratch when Lexer
    calls for the merge; do not fold in until the economy is mature

142. TRAPPER / FENCE RECIPE OWNERSHIP AUDIT — verify whether moving every
    Trapper and Fence recipe to portable campfire crafting broke its material
    semantics. Determine whether sold pelts become merchant-held persistent
    material credits that can satisfy multiple garments, whether those credits
    are inaccessible to player crafting, and which clothing recipes therefore
    must remain Trapper-owned. Perform the same audit for Fence recipes and
    identify any shop-owned unlocks, services, or ingredient pools that cannot
    be reproduced at a campfire. Restore only the recipes that genuinely depend
    on their merchant, while leaving ordinary player-craftable recipes portable.
    Waiting on the audit and Lexer's final decision about merchant exclusivity.
	
	~ Or maybe just make legendary pelt craftables craftable with renewable stuff? Then what will legendary parts be used for?

141. HORSE TACK EFFECT AUDIT AND REWORK — audit every saddle, stirrup, saddlebag,
    horn, blanket, bedroll, and related horse-tack effect; determine what each
    value actually changes, resolve and name its records in LEXEDITOR, and show
    useful vanilla/reference values. Then redesign tack effects so equipment
    choices have distinct, meaningful gameplay roles rather than redundant or
    opaque stat bonuses. Waiting on Lexer's preferred tack roles and balance
    after the verified effect audit is available.

99. CHALLENGE LIST REDESIGN — Redesign challenge lists.
100. GAMBLING ANTI-EXPLOIT LIMITS — Gambling anti-exploit measures: "After winning versus all opponents, the last one remains and allows the player to replay him as many times as wanted for bets between $25-$100. This is a quick way to make a lot of money if the player is good at it.After winning versus all opponents, the last one remains and allows the player to replay him as many times as wanted for bets between $25-$100. This is a quick way to make a lot of money if the player is good at it."
Should keep this in mind and make changes to all gambling in general to adjust. Also think about the exploitability of gambling + the ability to save and load freely. Maybe put diagetic limits on all gambling in a similar way -- after a game of poker, for example, everyone leaves and doesn't come back for maybe a week or so -- reduce betting limits, make it so you can't start a gambling game within 5 after loading a save, etc.

104. HORSE STAMINA CORE RESTORATION — Design horse stamina core restoration. I think there's a mod that adds horse thirst. Maybe look at that, use as reference, recreate that feature from it?
105. THIRST CORE AND ALCOHOL-FREE STAMINA RESTORATION — Similarly, there's a mod that adds a thirst core and ways of filling it in. I should take a look at recreating parts from that as we need alcohol-free means of stamina core restoration.

110. TONIC RADIAL-MENU USAGE INDICATORS — Do the new tonics have usage indicators in the radial menu that look righta?

115. VARIED DIET REWARD — Some kidn of varied diet boost. Maybe just some kind of "eat x different meals" reward or goal somewher.

118. COMBAT REDESIGN: ROLLS, ENEMY RHYTHM, ENEMY DEAD EYE — Readding rolls would be easy.  Making them useful would be hard. A total combat redesign is warranted. Regular, rhythmic enemy shots. Starting-area enemies shoot extra slow and predictable, one by one. Give enemies firebottles and let them use them, mix in melee enemies or even add enemies who can melee or shoot. Let enemies perform a throwing knife attack with long windup so you know to dodge in advance. Maybe add officer-level enemies who fight on horsebcak while their minions fight on foot, if they have eyes on you out of cover for X seconds continuously you hear that bell chime sound and THEY use deadeye on you!!! that would be really cool, letting enemies deadeye you
https://www.nexusmods.com/reddeadredemption2/mods/7421
https://www.nexusmods.com/reddeadredemption2/mods/6687

120. HORSE TONIC CAPACITY UPGRADES — Design player horse tonic capacity upgrades.
121. CHAPTER COMPLETION REWARDS — Some kind of reward(s) for completing each chapter. Or unlocks? As-is there's like....zero reason to
122. STRANGER-MISSION TRINKETS — Each stranger mission/mission tree should give you a trinket. https://reddead.fandom.com/wiki/Missions_in_Redemption_2#Stranger_Side_Missions
123. BANK ROBBERIES — Bank robberies: self explanatory. Will have to check out this mod and maybe some others for the precise design and implementation
https://www.nexusmods.com/reddeadredemption2/mods/7289


126. BOTANIST CHALLENGE REWORK — Botanical challenge rework:
each of the 10 challenges should just be "complete X% of the plant compendium". Challenge 10 gives you the Golden Shears, which 10xs tonic drop chances.
127. SURVIVALIST CHALLENGE REWORK — Survivalist challenge rework:
"cook all 11 types of meat" can be just copied from the vanilla rank 10 herbalist challnge iirc
128. AREA DIFFICULTY REWORK — Area difficulty rework: massive. Take a look at the order in which players were meant to travel through the game based on I guess where you go in each chapter. Change the difficulty of the areas accordingly -- enemy HP, shop prices, enemy drops, etc.
129. HORSEMAN CHALLENGE REWORK — Horseman challenges rework:
Each challenge stage complete increases horse health and horse stamina tonic capacity by +1 and increases bonding speed by 10%, as well as 
Completing Challenge 10 grants the golden horseshoe trinket, which lets you revive your horse simply by laying hands on it.



62. CARRY CAPS & CARRY-CAP UPGRADES REWORK
	- Drinks pouch and food pouch -- each of these could be a slot on the radial menu

34. CHALLENGES REWORK

35. REWORK GUN BELTS, HOLSTERS, BANDOLIERS, AND SATCHEL UPGRADES — how do they, in vanilla, do all these different kinds you get from the challenge trees interact with the normal ones you can just buy at all times? What should they do? Umm I think I'm getting rid of some of their effects and putting them into challenge rewards?

37. REWORK CHARMS
	- https://reddead.fandom.com/wiki/Talismans_%26_Trinkets
	- Remember to actually implement these items and their effects.
	- When you complete the criteria, you get the trinket added to your inventory, with a popup (the ones that pause the game and require you to hit "OK" to close) that comes up saying what it does and why you earned it.
	- Can we get a seperate Trinkets tab in the inventory menu? That would be great, so the player could see all their trinkets at once.
	- If the trinket can be obtained through any other means in the normal game, like finding it in the world or crafting it, those methods should be removed.
	- The exception should be the arrowhead obtained when you collect all the dreamcatchers -- in this case, the popup should say to check your journal to find its location.
	- I need to be able to edit the log text of these tasks to include their rewards.
	- The descriptions in brackets are just for me to easily remember which I've designed yet. Check their descriptions for how they should actually behave. Unless I forgot to fill them in, in which case, point it out first and make me fill them in first.
	- IDK so like we need to give these like a custom group or category or something to give them their own satchel category? Anyways once we do that they should have their own subtab in items, OK?
	- Wait, a bunch of these have existing effects in the vanilla game. But nothing in the effects column. So, uh, how do we remove their effects? Would be really cool if we could just make custom effects for my new talismans and then add and edit them in the editor the same way they (assumedly) would for vanilla talismans.
	- These might need some kind of safety to prevent them from being obtained in their vanilla game way -- crafting, found in world, looted, there are so many different ones that surely one will fall through the cracks...but how to implement such a thing?
	
	- Chapter 1: Antique Compass (+1 Deadeye Tonic Level)
	- Chapter 2: Ram Horn Trinket (+1 Health Tonic Level)
	- Chapter 3: Wolf Heart Trinket (+1 Stamina Tonic Level)
	- Chapter 4: Alligator Tooth Talisman (+1 Deadeye Tonic Level)
	- Chapter 5: Bear Claw Talisman (+1 Health Tonic Level)
	- Chapter 6: Bison Horn Talisman (+1 Stamina Tonic Level)
	- Epilogue 1: Eagle Talon Talisman (+1 Deadeye Tonic Level)
	- Epilogue 2: Raven Claw Talisman (+1 Health Tonic Level)
	- Bandit Challenges: Deputy Badge (+50% Police Stealth)
	- Explorer Challenges: Brass Compass (Fast Travel)
	- Gambler Challenges: Cougar Fang Trinket (6x Final Shot Revolver DMG)
	- Naturalist Challenges: Coyote Fang Trinket (Instant Crafting)
	- Horseman Challenges: Elk Antler Trinket (Horse Revival)
	- Hunter Challenges: Fox Claw Trinket (50% Animal Stealth)
	- Sharpshooter Challenges: Iguana Scale Trinket (2x Deadeye Regen)
	- Survivalist Challenges: Moose Antler Trinket (TODO)
	- Weapons Expert Challenges: Owl Feather Trinket (TODO)
	- All Challenges: Panther's Eye Trinket (TODO)
	- Animal Compendium: Pronghorn Horn Trinket (TODO)
	- Equipment Compendium: Catseye Trinket (TODO)
	- Fish Compendium: Crow's Beak Trinket (TODO)
	- Gangs Compendium: Tatanka Bison Horn Trinket (Offscreen Enemies +50 DEF)
	- Horse Breeds Compendium: Boar Tusk Talisman (2x Horse Stamina Regen)
	- Plant Species Compendium: Hawk Talon Trinket (+25% Harvest Chance)
	- Weapons Compendium: Shark Tooth Trinket (No Weapon Decay)
	- All Compendium: Turtle Shell Trinket (TODO)
	- Graves: Buck Antler Trinket (HP Regen)
	- 10 Dreamcatchers: Ancient Arrowhead
	- Bounty Hunter: Beaver Tooth Trinket (Lasso targets from 2x distance)
	- 15 Dinosaur Bones: Quartz Chunk (TODO)
	- 30 Dinosaur Bones: Skull Statue (TODO)
	- 2 Card Sets: Fluorite (+1 Horse Health Tonic Level)
	- 4 Card Sets: Ammolite (+1 Horse Stamina Tonic Level)
	- 6 Card Sets: Fluorite (+1 Horse Health Tonic Level)
	- 8 Card Sets: Ammolite (+1 Horse Stamina Tonic Level)
	- 10 Card Sets: Fluorite (+1 Horse Health Tonic Level)
	- 12 Card Sets: Ammolite (+1 Horse Stamina Tonic Level)	
	- 10 POIS: TODO (+10% Move Speed)
	- 10 POIS: TODO (+20% Move Speed)
	- 10 POIS: TODO (+30% Move Speed)
	- 10 POIS: TODO (+40% Move Speed)
	- 10 POIS: TODO (+50% Move Speed)
	- 4 Treasures Found: Ancient Necklace (2x Minimap Range)
	- 9 Treasures Found: Ancient Viking Comb (3x Minimap Range)
	- Rock Carvings: Rock Statue (TODO)
	- 3 Hunting Requests: Native American Ring (-25% Health Core Drain)
	- 5 Hunting Requests: Native American Ring (-25% Health Core Drain)
	- Legendary Animals:
	- Legendary Fish:
	- 100% Completion: 

Abalone Shell Fragment
Female Fertility Statue
Male Fertility Statue
Gold Shield
Native American Ring
Vintage Civil War Handcuffs
Shrunken Head
Aged Pirate Rum
Ginseng Elixir
Valerian Root


(No Deadeye Core Drain)
(2x Stamina Regen)

	- Orchid Missions:
	- Shacks: 

- Oh wait what are we gonna do with legendeary animal parts since we can't craft talismans from them now? Oh, maybe you get 1 part from each of the 7, then combine them all to make the trinket...

29. SIDEQUEST REWARDS REWORK: Ciggy cards, dino bones, and others. Review and possibly rework rewards.

make the semi-auto shotgun only appear once you hit 1907. maybe do the same for things that are nearly anachronistic?
look at distrubitions of all herbs. create new recipes for all levels of all tonics based on this.
same for predator bait and cover scent.

</Waiting_on_Lexer>

<Testing>  (Should be done. Needs confirmation.)

166. CUSTOM COLLECTIBLE MAP ICON PIPELINE — the failed external-dictionary
    route has been replaced with a complete resident `blips.ytd` override:
    all 321 vanilla sprite names plus the six reviewed collectible sprites.
    LEX_BLIP_CARD/BONE/CARVING/DREAMCATCHER/GRAVE/TREASURE are registered in
    update_4 `blipdata.ymt`, resolve through the resident `blips` dictionary,
    and are active again in GameplayTweaks. CONFIRM after a complete restart:
    all six custom icons render on the Story map and Index, and ordinary
    Rockstar blips remain intact rather than black or missing.

59. PERSISTENT FULL VANILLA CAMPSITES — tapping F4 validates the current outdoor
    ground position, saves it to `campsites.csv`, immediately creates a normal
    campsite map marker, and launches Rockstar's `player_camp` script at that
    exact position. Holding F4 for 0.8 seconds while within eight metres of an
    authored site removes its saved record and map marker. Nearby authored sites are materialized through the same
    script, retaining vanilla sleep, cook, craft, wardrobe, and fast-travel
    behavior rather than using decorative props. At an inactive site, hold the
    Activate Campsite prompt to persist activation and switch its placeholder
    map icon; death relocates Arthur and his living saddle horse to the nearest
    activated site. Invalid interior, water, steep-ground, duplicate, mission,
    and unavailable-player placements are rejected with an on-screen message.
    CONFIRM after the next complete restart: place one valid and one invalid
    site; verify the full camp interaction set, both placeholder icons,
    activation persistence after restart, and death respawn. Proper icon art is
    separately actionable as TODO 186.

167. MARKED-ONLY MINIMAP AWARENESS [CLASS A] — recon should suppress ordinary
    free-roam enemy dots for unmarked non-law targets while preserving cops,
    mission/objective blips, and every mission's normal awareness UI. A marked
    neutral that becomes hostile must change from grey to red immediately.
    CONFIRM outside a mission: mark a neutral and provoke them; verify their
    marker changes red, unmarked hostile companions remain absent, and lawmen
    retain Rockstar's normal dots. Then confirm no suppression occurs during a
    mission. This acceptance item is not satisfied merely because recon's own
    entity blips render.

113. BINOCULAR RECON TAGGING + 114. ENEMY HEALTH BARS — implemented 2026-07-25
    in GameplayTweaks.asi. Hold a living ped within
    `AimToleranceScreenRadius` through binoculars or while aiming for
    `StudyTimeMs`; projected apparent size uses current FOV, so binocular and
    scope zoom increase effective tagging range. Target eligibility uses one
    continuous eight-corner projected-bounds extent that responds to model
    dimensions, viewing angle, distance, FOV, and zoom without animal-size
    buckets. The native Study progress prompt fills during a new valid
    observation and hides for an existing tag.
    A marked target gets a persistent UI-layer placeholder icon, metre distance,
    and a near-continuous layered 100-HP health ring (red first layer, yellow
    second); its marker
    can remain visible through cover after the line-of-sight scan. Marked-only
    entity blips use Enemy/Companion/PickupAnimal styles for red/blue/yellow.
    Each uses Rockstar's real `AUTO_MODIFIER_COP_SEARCH_CONE` heading cone and
    follows target heading. Reconning a valid animal or horse invokes
    Rockstar's own observed/studied compendium path. Tags use the head bone
    rather than the body core. The player's saddle horse is always tagged with
    the owned-horse minimap glyph and its overhead tag hides while ridden.
    CONFIRM: hear the marking
    click for every newly marked target; mark by binoculars, iron sights, and a
    scope; mark an enemy, neutral/animal, bird, horse, and ally; verify animal/
    horse study progress, player-horse auto-tag/hide-while-ridden behavior,
    head anchoring, marker visibility while looking toward and away from the
    target, UI health layers above and below 100 HP, all three minimap colors, and a
    correctly oriented field-of-view cone around every marked minimap blip.

70. SHARED AMMO-FAMILY CAPS — implemented 2026-07-24. Each family gets ONE
    combined capacity via [SharedAmmoCaps]: every variant's own ceiling is raised
    to the shared number with _SET_PLAYER_MAX_AMMO_OVERRIDE_FOR_AMMO_TYPE
    (0xE133C1EC5300F740, PLAYER namespace) so any single variant can fill the
    pool, then every 250ms the family is summed via GET_PED_AMMO_BY_TYPE and any
    overflow is trimmed with SET_PED_AMMO_BY_TYPE — taken from whatever variant
    just increased (so the round you picked up last is the one that doesn't
    stick), falling back to the largest stack. Families: Pistol(.225)
    Revolver(.307) Repeater(.444) Rifle Shotgun Arrow Varmint(.22); _AMMOBOX
    entries are shop items, not ammo types, and are excluded. All caps default 0
    (= vanilla per-variant) until Lexer sets numbers.
    CONFIRM: set e.g. Revolver=100, then carry a mix of .307 types and check the
    combined total stops at 100 and excess pickups do not stick.

151. BINOCULAR FLOATING-MODEL GLITCH (keyboard F) — raising binos with F briefly
    showed the binocular model floating ~3ft to the side. Probe-confirmed cause:
    keyboard F = INPUT_PICKUP (0xe6360a8e); its reach-for-item animation displaced
    the model. Suppressing INPUT_PICKUP was NOT enough: by the time the ASI can
    disable the control the pickup TASK has already started, so equipping mid-reach
    still floats the prop. Fix v2 (2026-07-24): cancel the task itself —
    CLEAR_PED_SECONDARY_TASK(ped) at equip time and every frame during the
    keyboard pre-equip hold window. CONFIRM: hold F to glass — model should stay
    in-hand, no floating. (Gamepad was never affected; its button isn't a pickup.)

147a. COLLECTIBLE COLLECTION-CLEARING — implemented 2026-07-24. Each marker now
    carries a `collected` flag; when the player comes within [CollectibleMap]
    ClearRadius (default 6m, 2D) of a marker its blip is removed and the key
    (category|name) is appended to collectibles_collected.txt so it stays gone
    across sessions. refreshCollectibleBlips skips collected markers; the loop
    runs clearReachedCollectibles every 500ms while the player has control.
    AutoClearOnReach toggles it. Delete collectibles_collected.txt to reset.
    CONFIRM in-game: markers vanish as you reach them and stay gone on reload.
    (Note: with imprecise coords #147b, a blip may clear on approach without an
    actual pickup — acceptable for a finder aid; tighten ClearRadius if needed.)

116. BINOCULAR ACCESS REWORK — Hold F (keyboard) or RS / right-stick click
    (controller) past `[Binoculars] HoldMs` (default 250) equips owned
    WEAPON_KIT_BINOCULARS / _IMPROVED and forces look-through; release restores
    previous weapon. NEVER triggers while aiming a gun (IS_PLAYER_FREE_AIMING /
    TARGETTING) — the old Dead-Eye/special-ability trigger was removed 2026-07-24
    because it aliased RMB-aim. F read via GetAsyncKeyState, RS via XInput
    (XINPUT_GAMEPAD_RIGHT_THUMB). HoldMode: key / rs / both (default). RequireOwned=1
    never free-grants. Built into GameplayTweaks.asi — full restart required.
    Test: hold F with kit, hold RS with kit, hold with no kit, aim a gun (must
    NOT raise binos), on foot / horse, release restores weapon.

73. OLEANDER POISONING — consuming Oleander Sage now activates the ASI-owned
    Toxic state and status icon. Health Cure, Opened Health Cure, Potent Health
    Cure, and Special Health Cure clear it. Test Oleander activation, restart
    persistence, each cure, repeated consumption, and the displayed status.

74. TOXIC DAMAGES HEALTH BAR — Toxic now drains the outer Health bar over
    `[Toxicity] HealthBarDrainHours` in `GameplayTweaks.ini` instead of draining
    the Health Core. Test at full/partial Health, during combat, after sleep,
    across save/reload, and verify death behavior at zero Health.

75. HEAT DRAINS STAMINA CORE — the ASI reads the clothing-adjusted temperature
    attribute and drains Stamina Core in excessive heat. Base duration and the
    heat multiplier are configurable under `[Temperature]`. Test several hot
    regions/outfits and confirm Health Core is not charged for the modded tick.

76. COLD DRAINS HEALTH CORE — the same temperature controller drains Health
    Core in excessive cold, with its own configurable multiplier. Test several
    cold regions/outfits and confirm Stamina Core is not charged for the modded
    tick. Native weather penalties must not double-charge either core.

144. THREE-CALIBER CARTRIDGE AND CASING ICONS — distinct monochrome .225,
    .307, and .444 loaded-cartridge and spent-casing art is generated, packed
    into `LEX_INVENTORY_ITEMS.ytd`, assigned to the corresponding catalog ammo
    and casing records, and installed with the rebuilt ASI. Shotgun keeps its
    separate shell icon. Verify all six icons in the wheel/satchel, acquisition
    feed, and casing pickup UI at normal game scale.

85X. COLLECTIBLE SPENT CASINGS — v3 rewrite installed (2026-07-19 22:05).
    Casings are now plain physics objects (the engine cannot auto-vacuum
    them) collected via the game's own UIPrompt system: stand within 1.8 m,
    hold the loot key, get the item + a frontend pickup sound. Ejection
    timing is real per family: pistols eject just after the shot; revolvers
    keep brass in the cylinder and dump it all when a reload starts;
    repeaters/rifles/snipers/shotguns eject on the lever/bolt/pump cycle
    (weapon-ready edge), not at the shot. Bend-down anim is an ini hook
    (PickupAnimDict/Clip), blank until a verified clip name is sourced.
    TEST: fire each family, watch marker timing, hold loot key near a
    casing, check satchel + sound, then read GameplayTweaks.casings.log.
    KNOWN GAP: vanilla shell-eject VFX still duplicates our casing until
    the weapons stack ships complete (see item 87).

87. WEAPONS STACK EXTRACTION - root cause of the weapons.ymt saga found
    2026-07-20: weapon data is layered (base weapons.ymt + 6 pack_patch
    per-weapon ymts + 4 weaponcomponents.meta layers); shipping only the
    base file reverts Rockstar's own patches (double-fire/lantern/holster
    were pre-patch behavior, not corruption). NEXT: extract vanilla-final
    copies of all 11 files (OpenIV, game closed - the RPF8 CLI cannot read
    the nested update-content archive), verify zero behavior change, then
    retest the editor's blank-shells checkbox (server.py now refuses
    weapons edits until the stack is complete and maps all 11 files).

33. REMOVE CHILD INVINCIBILITY — GameplayTweaks uses the engine's own child-ped
    predicate and repeatedly clears invincibility and damage proofs on nearby
    children during ordinary free roam. It deliberately does nothing while the
    mission flag is active, preserving scripted/story protections. Test ambient
    Saint Denis street children and confirm missions involving Jack/children are
    unaffected.

44. VIKING COMB REWORK — carrying PROVISION_DISCO_VIKING_COMB now doubles a
    small positive Honor gain that follows the positive social-interaction
    control. Mission honor, antagonizing, losses, and gains over 20 points are
    excluded. Test several successful greetings with and without the comb.

46. VIKING HATCHET REWORK — free-roam corpses whose exact death source is the
    player and cause is WEAPON_MELEE_HATCHET_VIKING are tagged. When that exact
    corpse finishes being looted, GameplayTweaks adds four times the cash that
    interaction actually produced, leaving item loot untouched. Mission kills
    and authored mission payouts are excluded. Test cash/no-cash victims and an
    ordinary hatchet control kill.

132.  MERCHANT BUYER EDITING — LEXEDITOR's Shops > You Sell view now edits both
    resale payout and the independent PDATA_SHOP_INVENTORIES acceptance lists
    with one toggle per merchant type. GameplayTweaks captures a clean vanilla
    baseline to `vanilla_shop_buyers.csv` on the next Story Mode startup; the
    editor imports it, preserves unresolved hashes, and saves the complete
    from-scratch replacement to `MyOverhaul/parseddata/0x0BA63B3D.ymt`. Verify
    the baseline populates, make Tomahawks and all finite baits acceptable at
    the intended merchants, save, restart, and test actual sales in game

1.  OUTER BARS ONLY / NO CORE RESERVES — built and staged at the canonical
    GameplayTweaks.asi path for the next game restart. Empty outer Health now kills immediately; empty Stamina
    blocks sprint and forces active player/mount locomotion down to non-sprint
    speed without changing depletion to zero, so it cannot spill into
    the Stamina core; empty Dead Eye disables Dead Eye until the outer ring is
    refilled. `[NoReserveCores] Enabled=1` hot-reloads. TEST separately with
    nonempty cores: take Health to zero and confirm immediate death; sprint an
    empty Stamina bar and confirm its core does not fall; drain Dead Eye and
    confirm it exits without spending its core. The first Dead Eye test failed:
    its cached amount did not expose the ring/core boundary. The 2026-07-15
    build now reads the actual Dead Eye outer-ring native, watches the live Dead Eye core while Dead Eye is active,
    restores the first reserve tick, and disables the ability immediately.
    The 2026-07-16 build latches player and horse sprint exhaustion: recovery
    cannot restart sprint while the key/button remains held; the physical
    sprint control must be released and the bar must recover at least 2%.
    Retest. Also confirm ordinary passive
    core drain, food/tonic refills, sleep drain, missions, fades, and respawning
    still work. This is ASI enforcement, not a discovered engine toggle.
43. LOW-HONOR FENCE PRICING — at fences (incl. wagon/horse fence), the honor
    price curve is MIRRORED: rank -8 pays the Rank+8 multiplier (0.50 default)
    and rank +8 pays the Rank-8 one (1.50). Regular shops unchanged. The
    Executioner's-Mask exemption is skipped at fences while reversed (low
    honor is already the good side there). Ini: [HonorPrices] FenceReversed=1.
    Built on the existing cash-delta correction + fenceActive() detection.
    Auto-installs when the game closes (was running at build time); needs a
    restart after that. TEST: at low honor buy from a fence (should be cheap)
    and a general store (should still be penalized); flip at high honor.
55. AMMUNITION BREAKDOWN CRAFTING CATEGORY — built and installed as a real
    seventh portable-crafting filter. GameplayTweaks extends the live
    CraftingDatastore from six filters to seven and injects every output listed
    in breakdown_recipes.csv under BREAKDOWN. LEXEDITOR's Crafting tab exposes
    that assignment in its Menu category column. MyOverhaul adds LEX_GUNPOWDER
    material with five alternate always-known dismantling recipes: 10 regular
    revolver, pistol, repeater, or rifle rounds, or 5 regular shotgun shells,
    produce 1 Gunpowder. Test that the seventh filter appears, displays the
    localized row/icon, cycles all five inputs, consumes the selected ammo,
    awards Gunpowder, respects its cap of 20, and returns safely to all six
    vanilla filters. This is the first runtime extension of Rockstar's
    hard-coded six-filter state machine, so crashes/list corruption are the
    primary regression checks. Specialized-ammo recipes that consume Gunpowder
    remain part of the later ammo-rework balancing pass.

56. TEST ALL MODIFIED BAIT UPGRADES — in game, buy, sell, and craft every bait changed. Bread, cheese, corn, cricket tins, and worm cans are in bait-shop purchase stock; verify the separate vanilla buyer database accepts each for resale.
    in the Items `UPGRADE` category. Confirm each shop purchase charges the
    configured price and grants the displayed effective output; confirm each
    recipe consumes the configured ingredients, produces the configured amount,
    respects carry caps, appears at the intended crafting station, and leaves
    Bread, Cheese, Corn, Worm, and Cricket bait finite and consumable.

47. UNIVERSAL CRAFTING FEATHERS — all ordinary bird feather yields in
    loot_items_matrix.meta now become Flight Feathers, and every crafting recipe
    that formerly required a species-specific feather now consumes Flight
    Feathers. Exotic plumes remain distinct for their collection missions.
    Data validation passes; confirm bird skinning yields and several edited
    recipes in game after MyOverhaul is installed/reloaded.

133.  BANDIT CHALLENGE REWORK + MASK POWERS — MyOverhaul is installed and ranks
    now follow the edited descriptions: 50 town hold-ups; 10 fenced coaches;
    20 cash registers; 20 robbed coaches (fenced coaches no longer count and
    the hidden one-day reset is gone); $500 bounty; 25 fenced horses; 50
    stealth kills/knockouts using Rockstar's duplicate-safe stealth counter;
    500 human kills; one victim hogtied on train tracks; then rank 10 completes
    from sequential strand progression. Ranks 1–3 and 5–9 unlock Metal, Pig,
    Executioner, Sack, Cat Skull, Slasher, Ram Skull and Pagan Skull masks.
    GameplayTweaks applies their described equipped effects plus the permanent
    rank-10 law-perception reduction and configurable honor shop multipliers.
    Test every counter, unlock, equipped-item detection, cash/bounty/honor
    correction, witness behavior, combat modifiers, horse recovery, bounty
    hunter suppression/fleeing, and law perception. Rank 4 is deliberately
    incomplete: its Outlaw Pass glasses asset and an exact wanted-search-radius
    setter/hook are not yet identified, so no fake unlock/effect was shipped.

134.  IMPROVED IRON-SIGHT DIFFERENCE — verify whether the increased catalog
    effect assigned to improved/wide iron sights produces a noticeable in-game
    change. Important diagnosis before testing: the shared catalog effect
    `0x28C28678` is Value 5 / Percent 5 and may only describe the displayed
    benefit; actual sight mechanics live separately in weaponcomponents.meta
    (`CameraFovModifier`, vanilla commonly 0.95 versus 1.0 default). Confirm
    what the current edited effect changes, if anything, before treating it as
    a finished mechanical buff. A real retune likely requires adding our own
    vanilla-derived weaponcomponents.meta replacement.

28. COLLECTIBLE MAP TRACKING — built and installed in GameplayTweaks. Adds
    581 named, category-specific map/legend blips: 144 cards, 30 bones, 10 rock
    carvings, 20 dreamcatchers, 9 graves, 235 exotic locations, 57 Points of
    Interest, 14 legendary fish, 41 shacks, and 21 treasure clues/maps;
    deliberately excludes the eight actual treasure caches. Cards, bones,
    carvings and fish unlock when their introductory document is received;
    Algernon items unlock stage-by-stage from his five request lists. Every
    category hot-reloads from [CollectibleMap] in GameplayTweaks.ini. The first
    test exposed SHOP-style, invalid-sprite, and per-location Index problems;
    the rebuilt version uses vanilla coordinate blips, verified map-atlas
    sprites, and
    one shared Index label per category for 1-of-N cycling. Retest grouping,
    every category icon, location projection, unlock detection, and the practical
    blip limit. Automatic hiding of completed locations is not yet claimed.
    Known vanilla-UI limitation: the Index counter clips its right arrow for
    three-digit groups such as 144 cards. There is no blip native controlling
    that Scaleform layout. Preserving one Cards category therefore requires a
    map-menu UI patch; the data-only fallback is splitting cards into sets.
    Revised icon art is reviewed in GameplayTweaks/icons/map-icon-proposals.html:
    the six custom markers are AI-generated raster artwork; extracted vanilla
    sprites supply the remaining categories, with black medallions composited
    behind plant/paw/fish while POI remains unchanged. Every marker is shown at
    actual 24 px size. Nine custom/medallion textures are now packaged in
    `lex_map_icons.ytd`, but testing proved that loading a YTD does not register
    arbitrary hashes as blip sprites. The current retest build uses valid
    vanilla collectible glyphs for every category so none render blank; custom
    art remains future custom-UI work. Dinosaur-bone gating now accepts either
    possession or the persistent unlock state of its intro document. Retest all
    icons and confirm the 30 bones appear after A Test of Faith.

19. STAMINA CORE DRAIN ON WAGONS — built into GameplayTweaks. Enumerates all
    draft-harness slots on the player's moving wagon and drains each attached
    horse's stamina core. INI: WagonCores DrainPerSecond/MinimumSpeed.

21. IN-GAME-TIME CORE METABOLISM / SLEEP RETUNE — built and staged in
    GameplayTweaks for the next game restart. While awake, Health, Stamina,
    and Dead Eye cores each drain from 100 to 0 over their independently
    configurable `[CoreClock]` DrainHours (24 in-game hours by default). It
    replaces Rockstar's background metabolism rather than stacking on top of
    it, while accepting positive core changes from food, tonics, and scripts.
    During detected sleep, Health and Stamina continue draining at those rates
    while Dead Eye refills from 0 to 100 over DeadEyeSleepRefillHours (12 by
    default). TEST exact 24-hour drain, the 16-hours-awake + 8-hours-asleep
    cycle, ordinary clock passage, item refills, and false positives from fast
    travel/mission time skips. Specifically retest multi-effect provisions:
    both Kentucky Bourbon variants, crackers, canned corned beef, salmon,
    peaches, and pineapples. The live probe proved their item arrays load but
    selected definitions failed lookup. Vanilla and Kiddo tables are sorted by
    numeric effect key; MyOverhaul had 16 inversions. The installed test catalog
    now has all 373 definitions canonically keyed and sorted, and LEXEDITOR
    preserves that invariant on every save. Restart and verify every formerly
    missing effect plus its radial-menu icon.

4.  MINIMAP ZOOMED OUT — minimap shows more area (SET_RADAR_ZOOM each frame).
    GameplayTweaks.ini [Minimap] ZoomLevel — scale undocumented, tune live.

7.  ANIMAL SPAWN MULTIPLIER — global wild-animal density scale.
    GameplayTweaks.ini [AnimalDensity], OFF by default (Enabled=1 to try).

11. DYNAMIC STAMINA — human AND horse stamina drains faster and recovers
    faster (both 1.5x default). GameplayTweaks.ini [HumanStamina]/[HorseStamina].

</Testing>

<Complete>
130. RADIAL-MENU AMMO SCROLLING — confirmed in-game 2026-07-30. Mouse-wheel
    input inside the physical centre circle translates to Rockstar's native
    secondary-navigation ammo controls, updating the radial visibly. Outside
    the centre, mouse-wheel weapon cymbng remains vanilla; Q/E slot cycling is
    never suppressed. Centre detection reads the existing Windows cursor
    position without hooks or raw-input registration.

83. REMOVE LOADED CRIME-TWEAKS CONFLICT — removed the separate Crime Tweaks
    installation files and its enabled/load-order entries from the Story stack.
    MyOverhaul now solely owns crimeinformation.meta; the identical reference
    copy remains in datasets/crimeTweaks.

TODO: everything
-- lexeditor is now a thing
-- Nobody knows what the fuck the mask does. None of the wikis say what it does. If you look it up, you get a bunch of forum threads full of people who also have no clue what the mask does. This is 100% Rockstar's fault because they gave it such an unhelpful description. To be fair, the effect is a bit complicated (though still undoubtably substantial and useful), so the new, helpful descriptions are way too long. Still, no excuse for Rockstar to make such a glaring design error that the entire userbase has complained about for nearly a decade when it would take 5 minutes and cost $0.
-- Some of Pearson's crafting recipes made no sense, so I fixed them. Want to craft an alligator head? Cut the head off an alligator and throw it the fuck away because to make an Alligator Skull you don't need the head, just the skin. [So no head video]


Now that thirst is a concern, a number of new and fun drinks have been added to the game *. To make up for their lack of portability, beers in the saloon will now be considerably cheaper as a means of restoring your thirst, giving you an actual reason to drink in the saloon for once.

* Some of these drop tables would just be...objectively wrong. Like alligators dropping big game meat instead of herpetile meat, for some reason.
</Complete>

<Dropped>
149. L3 -> ITEM WHEEL PAGE — DROPPED 2026-07-24. Holding L3 correctly opens the
    weapon wheel (injecting INPUT_OPEN_WHEEL_MENU works), but NOTHING moves it to
    the items page. Tested every page-flip candidate control (INPUT_FRONTEND_RB —
    captured from the probe as the real control Lexer presses — plus
    SELECT_NEXT/PREV_WEAPON, FRONTEND_RIGHT/RT/LB) via _SET_CONTROL_NORMAL with
    tuned delay/hold/pulses; the wheel stayed on weapons every time
    (_HUD_GET_INVENTORY_WHEEL_CURRENTLY_HIGHLIGHTED kept returning a weapon hash).
    CONCLUSION: the wheel UI does not read script-injected controls, so this
    cannot be done by control injection. Would need a different mechanism
    entirely. The L3 crouch suppression and wheel-open behaviour still work if
    ever revisited.

158. PER-CARD MAP ICON NAMES — dropped 2026-07-24 by Lexer. Naming each cigarette
    card blip individually conflicts with keeping them in ONE index category: the
    map index groups blips by name, so unique names would create 144 separate
    index entries instead of one scrollable group. Lexer prefers the single
    grouped category, so cards keep the shared "Cigarette Card" name.

2.  Skills system — vanilla pause menu not extensible (hardcoded).
3.  Perfect-weight/mounted core-drain removal — engine-hardcoded.
5.  Deadeye regen from core instead of kills — kill-gain not removable.
26. Plant spawn-rate reduction — no true placement/spawn-density control has
    been identified. Scenario-point deactivation was rejected because it can
    leave visible plants unusable. Disabled in both project and installed INI.
18. Bounty maximum changes — no editable data, native, usable global, hook,
    or reference implementation has been found. Not buildable currently.
135.  CORE-EFFECT RAMP — dropped. Public AnimPostFX natives can play the vanilla
    low-core effect and adjust its potency, but cannot hold its animation at a
    static phase; manual activation therefore pulses instead of producing the
    requested steady linear ramp. Vanilla's steady presentation is driven by
    inaccessible engine logic. A generic custom vignette is explicitly not an
    acceptable substitute, and the exact Rockstar shader/assets are not
    available through the current extraction/runtime pipeline. All channels
    are disabled; the obsolete CoreVignetteRamp project source/configuration
    was removed and is not part of the Story-mode stack.
63. CUSTOM CHALLENGES MENU / NEW STRANDS — the vanilla `progress_menu`
    hardcodes nine challenge strand links, so data-only addition is disproven.
    Prototype a replacement Challenges page from GameplayTweaks.asi: first
    detect entry into the built-in Challenges activity, suppress it without a
    softlock, draw a minimal custom page above the frontend, and restore the
    Progress menu correctly on Back. If that probe passes, build the full
    RDR2-styled screen from challenges_sp/goals/localization with any number of
    strands. Do not attempt a brittle compiled-GFX replacement unless ASI
    interception fails.
64. CUSTOM IN-GAME UI FRAMEWORK — build reusable ASI primitives for arbitrary
    RDR2-styled panels, grids, horizontal tabs, lists, progress bars, scrolling,
    prompts, transitions, dynamic text/data, keyboard/controller navigation,
    proper mouse hit-testing, and custom texture support. Use it for the custom
    Challenges screen/new strands, Botanist and Zoologist Skills, challenge
    progress displays, additional crafting categories, richer item/effect
    information, and in-game mod settings. The UI does not itself unlock
    gameplay behavior: each feature still needs data, natives, events, globals,
    or a proven hook plus its own save/persistence handling.
    Put reusable editor/runtime support in a standalone `LexersLibrary.asi`
    companion that LEXEDITOR can configure but does not require. Keep overhaul-
    specific behavior in `Lexer's Mod.asi` (renamed from GameplayTweaks.asi).
    MyOverhaul may bundle both; public LEXEDITOR must remain useful without
    either ASI and expose runtime-only controls as unavailable when absent.
60. PER-STRAND SERIES / PARALLEL PROGRESSION — build this in the standalone
    runtime companion and restore the editor control only when it has a real
    implementation. The reference any-order mod proves concurrent ranks do not
    inherently require a custom UI: it splits ranks into separate challenge
    roots. That approach also creates duplicate strand entries, misreports
    pause-menu progress, resets progress through new IDs, and fails some
    script-score goals. Preserve one visible vanilla strand while the ASI owns
    rank activation/completion and save migration; use the custom Challenges
    page only if the vanilla grid cannot accurately present the resulting
    state.
</Dropped>

<Ideas>
RECON AWARENESS-STATE CORES — change each tag core's inner glyph/color with
    the target AI's live stealth-detection state: unaware, searching, or
    attacking. Keep the outer health ring independent so awareness and health
    remain readable simultaneously.

SALOON BAR BRAWLS — a marked brawl encounter at every saloon: starting
    one commits Arthur to an unarmed fight against the clientele. Each saloon
    could have a distinct crowd, fighting style, and ability mix; define start,
    fail, payout, law response, cooldown, and save-state rules before building.

- Premium cigarettes: make the on-smoke cigarette-card draw only give cards you
  do NOT already have, so premium packs are a meaningful way to finish sets
  instead of handing out duplicates. (Native per-card found-state exists, see
  #147, so "cards I am missing" is queryable.)

- Big idea: mention somewhere player-facing that horses are a huge expense that consumes as much food as 8 men daily. That way, we can make the upgrade from no horse to horse seem more substantial without just making them more expensive -- bad considering how often they die and get replaced (stealable too), oh but we'll also have to .... ah fuck what was i gonna type here....
- i'd really like wallet size upgrades (especilaly now that we have banking), but there's always the issue of what if your max bounty is higher? ooh, can i add partial bounty payoffs?
- halve all honor changes
- i'll be needing a source of triggering regular random tips to teach players about all my mod's features and changes. upon death, maybe? upon loaD?
-vantage points that fill in the whole region. like ubi towers.
-- Bounty hunters attack rework -- make them give you negative honor and increased bounty when you kill them, but they no longer count as always having you in combat and prevenitng you from doing other things as long as they're alive, no matter how far away. Instead, they go hunting for you and the challange will be to escape them. If you don't want to do the whole chase thing you can just kill them, but the penalty will be a higher bounty.
-- Great idea: as long as you have a bounty in a state, cops will be in the searching state where they're dark red on the minimap and get hostile when they see you. however, their density will be set by the amount of the bounty. Brilliant!
-- Need way more things to craft. Way, way more. Consumables are a bust, why not permanent upgrades? For example, upgrade trinkets to increase their potency.
-- On that note, maybe make them more like Dark Souls rings? Unlock more trinket slots somehow, choose loudouts for what challenges you're facing, and extra cool: int his game you can upgrade them yourself!
-- Showing side quests on the map -- great idea. But what about the ones you can't see on the map? Maybe the world map index should have entries for them, no locations, just tallies. better yet a jourrnal of sorts, but maybe that's far fetched? oh wait, maybe not, there is that public gui maker on github....



- Better loading screen tips mod. Seperate from mine. For vanilla. Make every item description say exactly what it does, elegant variation with LLMs, lists all recipes used in, whether or not it exists only to be sold, etc.
- Think of idea to reimplement oregano/thyme/theotherone meats.
- Think of idea to reimplement miracle tonics.
- Would it be possible to edit the mission medal requirements?
- Make it so mouse fwd/bckwd buttons cycle through ammo types in the tab menu. Or just in general, IG.
- There's that book. through woods andplains? seems destined to be a skill book or something. maybe make it so books grant permanent bonii.

- Compendium rework:
How you complete each stage of each compendium entry will be different, and comes with different rewards:
	Animals:
		None: See broad habitat and active time in compendium.
		1. Identified: Focus on it and hold "Study" to study X of them. Reward: shows up as "Unknown Animal" no more face-to-face and via tracks, making it easier to hunt down, can be flagged as tracked in compendium.
		2. Hunted: Kill Y of this animal. Reward: can now see animal quality and recommended kill methods in UI, see if calm, alerted, fleeing, or attacking, effective bait type, 
		3. Studied: Butcher Z perfect carcasses of this animal. Reward: Can now see drop tables in compendium, carcass value and decay time in UI, tracked, uh...tracks never time out, see loot before looting
	Equipment:
		None: Show the equipment and how to get it.
	Fish: TODO
	Gangs:
		None: TODO
		1. Identified: Study X individuals. Reward: no longer shows as "Stranger" in UI, can be tracked via compendium, improved drop chances
		2. Interrogated: Hogtie X individuals. Reward: always shows as red dots in UI, hideout shown on map, improved drop chances, drop table in compendium  (TODO: What do we do if the player goes to their hideout without reaching this point?)
		3. Defeated: Defeat their gang hideout. Reward: TODO, further improved drop chances, see loot before looting
	Plants:
		None: TODO
		1. Identified: Study X individuals. Reward: Gains ability to pick, track from Compendium
		2. Picked: Pick X individuals. Reward: increase to acquisition chance, ability to eat, TODO
		3. Tasted: Eat X. Reward: TODO, see loot before looting
	Horses:
		None: TODO (even at NONE, all things should show vague enough info in the compendium so you can actually find it!)
		1. Identified: Study X of them. Reward: shows up as "Unknown Animal" no more face-to-face and via tracks, making it easier to hunt down, can be flagged as tracked in compendium, can see stats in UI
		2. Ridden: Ride X unique individuals. Reward: Unlocks further bond levels with this horse type and TODO
		3. Bonded: Max out bond with one. Reward: See exact bond progress, 3x bond gain.
	Weapons:
		None: TODO
		1. Identified: Get your hands on one. Reward: Changes from "Unknown Weapon" in UI, can be tracked. 
		2. Used: Clean a total of X condition from this gun. Reward: unlocks further familiarity levels, TODO
		3. Mastered: Max out familiarity with it. Reward: TODO		
Compendium Completion Milestone Rewards:
		Overall Progression: 25% enable tracking from compendium to see the distance to the nearest instance of it, 50% distance and direction, 75% show on minimap...but I need more than just 3. What else?
		Cigarette Cards: Would be cool if handing in each set gave you a unique perk, maybe themed around the set itself? TODO
		Animals: TODO
		Equipment: TODO
		Fish: TODO
		Gangs: TODO
		Plants: TODO
		Horses: TODO, maybe sell stolen to any stable, not just fence?
		Weapons: TODO, maybe see a weapon familiarity bar UI?
- ideas: Take over a gang hideout to discover the locations of the other 5 on your map.
	Finish horse compendium = invincible horsey
	Herb pickup chance is 25%. Each 1% your herb compendium has = 0.5%+ pickup chance.

LOADING SCREEN TIPS IDEAS:
- To upgrade your maximum health, complete the TK located in Pause Menu -> TK
- Deadeye equivalent
- Stamina equivalent
- The world gets more dangerous the further you go south.

"The final word in RDR2 mods."


Bantit challenges might be the worst since you can only really use one mask at a time. Maybe add an extra bonus for each challenge completed, like -10% damage from cops or wanted search time or search mode time or bounty gain rate...




"If I catch you looking up how to do this online I'm showing up at your house and forcing you to uninstall RDR2.
That's like 75 gigs you gotta redownload."

make sprint-c

limbing and sprint-sneaking unlockables.
</Ideas>

<Notes>
Tonic Levels (For future DS-style upgrading):
I. Opened X
II. X
III. Potent X
IV. Special X

Fillingness levels:
	12.5%	slight	slightly
	25%	modest	modestly
	37.5%	moderate	moderately
	50%	considerable	considerably
	62.5%	substantial	substantially
	75%	great	greatly
	100%	complete	completely

	
-- Don't unskinned carcasses fetch higher prices from shops? But I don't see any seperate entries for skinned and unskinned carcassses in the items tab.
   >> ANSWERED 2026-07-14: there IS only one catalog item per animal x quality
      (verified across all 1,450 carcass references) — skinned-ness is state on
      the carried instance, not a second item. The butcher applies runtime
      PRICE MODIFIERS at the point of sale (shop_butcher.c calls
      _ITEM_DATABASE_GET_ITEM_PRICE_MODIFIERS), so the skinned discount is a
      multiplier over the one base price. The Items tab price = intact base;
      the skinned markdown can't appear as a row. Retuning that markdown %
      would be a separate dig into the price-modifier records — ask if wanted.

</Notes>


================================================================================
ARCHIVE — former docs/PROJECT_HISTORY.md, folded in 2026-08-04 (#194)
--------------------------------------------------------------------------------
Dated narratives, superseded investigations and per-session history. Kept whole
so nothing is lost. Anything in here that is still TRUE has been promoted into
CODEX.txt; treat this section as evidence, not as instructions, and never copy
from it without checking the codex first.
================================================================================

# Project investigation history (archived)

This is the former oversized AGENTS.md preserved for technical search and
historical context. It contains obsolete and superseded statements. It is not
an instruction file; current rules and confirmed facts live in `../AGENTS.md`.

# Former AGENTS.md — project memory for the RDR2 overhaul

Read this first. It is the durable memory for this project. **Maintain this
file**: whenever a durable fact, decision, constraint, or user instruction
emerges, record it here (including this instruction to maintain the file —
that recursion is intentional and requested by Lexer). Also keep
[TODO.txt](TODO.txt) and [CREDITS.txt](CREDITS.txt) up to date as part of any
change you make — update them in the same turn as the work, not later.
`FEATURES.txt` was deliberately deleted at Lexer's request on 2026-07-12; do
not recreate it or maintain a duplicate feature/TODO list.

