# #130: Build tonic refilling on shared overflow storage

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/130)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #30 worklog](github-130/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-30.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 dependency check

Re-read live #130 and #126 bodies/comments. #126 is still the installed one-item Baked Beans prototype, awaiting its stated test. Current overflow_storage.cpp rejects more than one CSV row and has one global prototype item. The old tonic_refill.cpp still exists on disk but is not included or called by script.cpp; it owns a separate reserve file. It is not an installed implementation of shared storage and must not be re-enabled as if it fulfills this request. Generalize the shared transaction and persistence owner before adding family capacities, highest-tier refills, death/camp triggers and exact shortage notices. Existing prototype human test remains separate; #130 remains actionable.

## Shared registry source implementation

The single-item limitation above was repaired in source in C:/RDR2Mod/GameplayTweaks/modules/overflow_storage.cpp. No catalog, shipped CSV, game file or #151 experiment file changed. The shipped registry still contains only Baked Beans. No tonic_refill.cpp include, second store or refill trigger was added.

The existing CSV now supports up to 64 unique item hashes. The loader caps the file at 16 KiB, lines at 256 bytes and item keys at 96 characters; it rejects invalid identifiers, duplicate hashes, malformed/extra columns, empty data and invalid authored/lifted bounds. Parsing builds a local candidate and publishes it only after every row succeeds. Each item owns reserve, last count, cap readiness and catalog readback state. Persistence still uses GameplayTweaks.overflow-storage.ini, [Reserve], and the exact symbolic item name, including the existing Beans key.

Startup reads saved counts as strict decimal text from 0 through INT_MAX. Missing keys default to 0. Invalid, negative, truncated or overflowed saved values disable startup without writing any key; every item is validated before preflight writes begin. Deposit quantity is bounded by remaining representable reserve space before inventory removal. One transaction guard covers all items and rejects nested transfers. Persistence failure stops the entire shared owner after the existing rollback attempt.

Background work processes at most four items per 250 ms tick, without catch-up bursts. One item retains 250 ms polling; 64 items take up to 4 seconds per full cycle. This is delayed overflow capture, not instant cap enforcement. A failed cap readback becoming valid, or a changed active cap, permits another transition check without a new inventory delta. Unchanged successful state does not cause repeated inventory writes.

The existing camp F7 page selects item types with Left/Right, shows selected-item localized text and counts, and keeps Up/Down for Withdraw/Deposit. Item changes consume the frame so a simultaneous Accept cannot transfer the prior item. Each transfer rechecks the selected item's live catalog/cap readback. Left/Right participate in the existing held-input release gates; Back retains ownership through its release frame. Full multi-item page visuals and controller use remain untested in game.

## Execution evidence

tools/verify_rdr2_overflow_registry.py compiles the actual production module with fake game/OS interfaces in a cleaned temporary directory. Passed: actual file loader, invalid-tail all-or-nothing parsing, duplicate hashes, 64-row limit, four-item poll bound and full cycle, Beans keys, missing/invalid/INT_MAX saves, no writes on corrupt startup, per-item cap/readback independence, exact two-item deposits, cap recovery, full reserve without removal, shared transaction reentry rejection, real UI item selection/Accept isolation, fresh transfer cap checks, failed-persistence rollback and original single-item cadence. Four behavioral mutants were rejected: duplicate hash acceptance, unbounded polling, cross-item reentry, reserve overflow. This is source execution evidence, not game acceptance.

The existing verify_overflow_storage_issue_26.py arithmetic token was updated to match the guarded engine-cap subtraction; its Beans-only shipped-data assertion remains. That old script's full catalog-copy check was not run in this source-only slice. Root owns the combined build and runtime delivery.

## Remaining full scope

#130 stays actionable. The shared registry is a dependency slice. Still required: proven Health/Stamina/Dead Eye family definitions; upgradeable shared carried capacities; highest-tier reserve selection; camp/death refill transitions; exact shortage notices; required catalog capacity changes and complete source tests; then controlled build/delivery after #151 and separate human tests. #126's purchase, grant, pickup, notification silence, camp transfer and save/reload tests remain open. Do not claim the old removed tonic implementation supplies these requirements.

## Recurrence audit

Read the old overflow verifier before the module and read the live issues/comments. Relevant failure classes from C:/RDR2Mod/fuckups.txt: source assertions mistaken for behavior, permanent inventory fights, duplicate ownership, shared-input leakage and claimed game acceptance from source. Primary evidence is the existing overflow transaction path and its simple_crafting.c cap-readback references, plus the existing camp/modal input implementation. No new native was invented; item display uses the hash-label lookup already used by casingDisplayName. The executable harness above is the agent-side proof. Gameplay notification, acquisition side effects, persistence across saves and rendered controls remain the player-visible acceptance boundary.

Combined development build passed: 334A268547E779406A80C5865FD4463DEE8E80FF2BF5FA3E4D352FBD88C22342. Candidate: out/rdr2-after-duration/GameplayTweaks.asi, matching release manifest. Not installed: duration experiment #151 remains active. Build log: out/rdr2-build-overflow-binoculars.log. Agent-side module tests passed; game acceptance remains open.

