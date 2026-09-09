# #220: Finish the two-mode vehicle camera handoff

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/220)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #128 worklog](github-220/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-128.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 vehicle candidate verification

Live issue confirms that foot and horse two-mode behavior was accepted; only vehicle handoff remains. Current production code owns the disabled release before reading it and forces one first/third selection each eligible frame. It yields during aim, loss of player control, vehicle exit, missions and cinematics. It now logs rendered first/third state alongside its selected state; a force call alone does not prove the result.

`tools/verify_rdr2_vehicle_camera.py --runtime-root C:/RDR2Mod` compiles and executes the actual production vehicle-owner function. It verifies repeated toggles, held selection, first-person entry, ownership release and truthful rendered-state telemetry. Four mutations fail: missing disable, missing first-person force, stolen aim input, and reporting the selected state as rendered. Existing `verify_two_camera_modes_issue_128.py` passes against the current native database and Story wagon call pattern. Temporary compiler files are removed on exit.

Integration must record the current build/install here or in its linked report before this is a delivered candidate. After that, the focused human check is: enter a wagon, cart or buggy in third-person free roam; press and release V twice. Each release must alternate between real first person and the one configured third-person view. Aim and exit must remain usable. Report which vehicle fails, the visible result, and the current camera-editor vehicle records. Do not repeat accepted foot/horse tests.

Integration delivery: installed combined ASI12C8E7078225280EF18E365FFB49EE6FBE92E3CB023B44F335D370308168DA81, source/game-root hashes match. Current rendered-mode heartbeat is available on next Story launch. Vehicle camera appearance remains unverified.

## 2026-09-08 follow-up scope review

Live #220 still asks only for the failed vehicle V handoff; accepted foot/horse checks must not be repeated. The earlier installed hash above is historical: #151 now owns the live game installation. Parent holds later candidates and must name the restored/delivered candidate before a new vehicle test. No additional vehicle-native change was justified by this review. Separate #108 source repairs now cover frame-rate-independent calibration and failure-aware profile saves; they do not claim vehicle height is solved.
