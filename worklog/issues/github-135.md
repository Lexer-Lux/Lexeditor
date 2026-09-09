# #135: Fix train detection before redesigning its markers

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/135)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #35 worklog](github-135/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-35.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 live engine ownership candidate

Live issue/comments and previous #35 handoff read. Driver-seat occupancy was the only remaining engine classifier; an empty or driverless locomotive was rejected even while live. Candidate now resolves the engine with _GET_TRAIN_CAR (671A07C9A1CD50A5) and accepts its live identity, without a driver requirement or three-model allowlist. Current1491.50 long_update uses this native then checks the resolved entity. GhostTrainSteamer and steamerDummy remain excluded. Ordinary streetcars are not excluded by name, per the latest distinct-streetcar-art requirement.

Current vehicle-pool ownership, entity checks, duplicate suppression, missing-blip recreation, stream-out retirement and tracking-off cleanup remain. New bounded train-map log reports vehicles, resolved engines and markers every three seconds. No stale track coordinate creates a marker.

`tools/verify_rdr2_train_tracking.py` executes production discovery/cleanup with controlled native readbacks. Driverless engine plus carriages produces one marker; ghost/dummy produce none; removed blips recreate; stream-out, despawn and disable retire markers. Four mutations fail. Tests do not prove _GET_TRAIN_CAR resolves every live variant from a pooled vehicle; new diagnostics expose that boundary.

Root owns build/install. Real train detection still needs runtime proof and distinct cargo/passenger/streetcar artwork remains incomplete. Keep actionable; do not present the common vanilla train sprite as the completed artwork request.

### Artwork boundary checked after detection build

Recovered the specific cargo/passenger/Saint Denis streetcar request and its later correction: separate sprite linkages can share BLIP_STYLE_TRAIN and its heading arrow. Passenger/cargo classification must inspect the live consist because engines can be shared; a mixed consist uses passenger artwork. Historical notes require the working full texture-dictionary replacement and reject the old standalone-dictionary path that produced black squares.

Inspected local vanilla `blip_ambient_train.png` and `blip_shop_train.png`. They are a generic live train symbol and a train-station symbol, not three suitable class-specific icons. No existing cargo/passenger/streetcar set was found in the icon tree. Live #138 requires showing variants and receiving visual direction before replacement. No art substitution or new asset was made. Next implementation needs reviewed distinct assets plus source-proven carriage classification; these stay actionable preparation work, not an unseen-art approval request.

## Local delivery, 2026-09-08

Development build passed. Installed ASI and matching release manifest with RDR2 closed; SHA-256 `EC0ECC477BE9089E3C17C25816580FD85D597A113236C94B3041E0E3504819E2`. Previous ASI retained as a small hash-named rollback copy. No catalog or settings changed. Production executable tests pass; rejected four train regressions and three card-conversion regressions. No game launch or rendered acceptance claimed. Full issue remains actionable.
