# #160: Choose truthful core-drain information for the Player page

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/160)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 exact bindings and source candidate

Live issue/comments read. Hiding the misleading drain time and rate values is authorized. The live issue's historical player_menu function names/PMPLAYER_CORE_CLOCK labels do not match the current1491.50 script. Current short_update func1624 constructs playerSkillsDatastore with rpgLines{row}{panel}; row2 is PMPLAYER_CORE_DRAIN_RATE, panels1/2/3 are Health/Stamina/Dead Eye. Funcs2876/2877 update time/rate presentation. Row1 is PMPLAYER_CORE_TIME and derives from the same vanilla drain forecast. Both rows1/2 must be hidden; core fill row0 remains untouched.

`player_core_rates.cpp` reads retained IDs with both array count cells included: base1954819+5+2+1+panel*36; value field12+1+row and arrow field32+1+row for rows1/2. It first requires active player_menu, CoreClock enabled, valid root, and the root global matching DB_GET_PATH("playerSkillsDatastore"). A changed build/store fails closed. It writes an empty string and hides arrows on those six time/rate rows only. No globals, core rates, core values, bindings, or UI containers are created/changed. Existing row binding strings are rewritten each eligible frame because Rockstar owns their refresh. No writes occur outside the active menu; Rockstar retains lifecycle ownership.

Direct string write/read hashes E1BD342F2872AEE9/3D290B5FFA7C5151 and BOOL write AB888B4B91046770 match the SDK. Bounded log reports actual empty-string readbacks, not rendered acceptance. `tools/verify_rdr2_player_core_rates.py` compiles production code against controlled bindings and proves inactive/disabled/mismatched-store guards, exact row IDs, and repeated writes. Four mutations fail. Small temporary compiler outputs are cleaned on exit.

Root owns dispatch/build/install. Candidate acceptance after confirmed delivery: open Player with CoreClock on, inspect Health/Stamina/Dead Eye; their drain time and rate values/arrows must be blank, while core fill and unrelated rows remain. Close the page and confirm normal gameplay. Render timing is not proved by these tests; keep actionable until delivery and remaining scope are resolved.

## Local delivery, 2026-09-08

Integrated after startup quarantine and outside gameplay-only pause guards. Development build passed. With RDR2 closed, installed GameplayTweaks.asi and matching release manifest; SHA-256 `4534F646B87AEDFD656CA8E0C5D401DDED5437E7A3139E554F7F7F007E99590F`. Previous ASI retained as one hash-named rollback copy. No settings or game data changed. Production C++ fixture passes and rejects four mutations. Whole Python suite: 326 passed, 4 skipped, 139 subtests passed.

Rendered acceptance remains: with CoreClock enabled, open Player and inspect Health, Stamina and Dead Eye. Drain time/rate values and arrows must be blank; core fill and unrelated values must remain. Close the page and confirm normal play. Report a screenshot and the player-core-rates log if any value remains. No game was launched by the agent. Issue remains actionable.
