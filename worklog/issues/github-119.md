# #119: Stealth detection indicators

[Live request and comments](https://github.com/Lexer-Lux/Lexeditor/issues/119)

## Scope

Show discrete directional warnings from observed AI states: ivory for hostile focused line of sight, amber for targeted suspicion or threat, red for combat. Do not invent a universal detection percentage. Do not hide warnings based on stance or movement. Exclude ordinary civilian glances; show at most four warnings with a brief hold and fade.

The full request still needs the remaining cover, lantern and weather comparisons in [#113](https://github.com/Lexer-Lux/Lexeditor/issues/113). The current #113 request supersedes older claims that all detection trials were complete. Do not repeat the completed movement/noise trials.

## Source repair, 2026-09-08

`C:/RDR2Mod/GameplayTweaks/modules/stealth_indicators.cpp` now:

- Hides and clears warnings while the HUD is hidden, a cinematic camera is rendering, or the current story animation scene is running. Existing pause, satchel, death, fade and custom-menu gates remain. On resume, the next update can scan at once.
- Checks each cached observer for existence, model change, death and age before reading its coordinates, including frames between 100 ms scans. Model matching detects a changed-model handle; it cannot prove that a reused same-model handle is the same actor.
- Computes each candidate distance once before sorting. Keeps the priority, nearest-first tie break, 65 m limit and four-warning cap.
- Uses the final rendered camera rotation for directional placement, so a scripted camera does not use a different gameplay-camera bearing.

The scene condition follows the already verified Recon guard: 1491.50 `camp_beaverhollow.c` function 624 checks `Global_43800` with `DOES_ANIM_SCENE_EXIST` and `IS_ANIM_SCENE_RUNNING`. The local SDK calls the same `0xCBFC7725DE6CE2E0` native `_IS_ANIM_SCENE_STARTED`. Cinematic camera state alone is not used to infer a story scene.

## Agent validation

`tools/verify_rdr2_stealth_indicators.py --runtime-root C:/RDR2Mod` compiles and executes the actual full module with controlled native results. It checks classification, uncertain sight and blocked LOS, civilian exclusion, combat, targeted flee, suppression and immediate resumption, despawn/death/model changes between scans, priority and distance ordering, cap, fade/expiry and final-camera bearing. Production passes; ten mutated branches are rejected. Basic unavailable, missing-player, pause and satchel guards run before any global or scene read; the harness verifies zero such reads in each case. A missing global pointer skips scene natives safely. Compiler files use a temporary directory with cleanup. This verifies code decisions, not actual AI or rendered behavior.

The existing runtime `tools/reverse-engineering/verify_stealth_indicators_issue_19.py` source guard also passes. Parent owns build and delivery. This source repair is not a new delivered candidate while the #151 experiment owns the game installation.

## Next work

Keep this issue actionable. Parent must build and deliver the source repair when the current experiment permits it. Prepare the remaining #113 sequence with the specified probe and manual lantern prerequisites. Then check warning direction and color against known observer states, ordinary neutral observers, standing/crouching/movement, story/cinematic suppression and resumption, and four-observer priority/fade in the rendered game. Do not claim detection thresholds, scene behavior or visual acceptance from the harness.

Root built and hash-verified this source, SHA-256 `B00DD107566D4680D371EEACCF5A0BCE24B38CD1D585FBB44A2BEB88AD98556B`. Candidate and matching release manifest are held under `out/rdr2-after-duration`; not installed while #151 is active. The build is not gameplay or visual acceptance.
