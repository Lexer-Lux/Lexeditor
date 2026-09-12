# #252: Fix falling and snapping during angled top-outs

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/252)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #160 worklog](github-252/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-160.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.


## Local repair preflight — 2026-09-08

Read live #252/#258/#251/#253/#193, their available comments, the imported
#160/#161 handoffs, current movement source, and the #159/#160/#161/#169 verifiers.
Read C:/RDR2Mod/fuckups.txt. Failure classes: a passing token check is not execution;
task acceptance is not completed traversal; a fall must not be called grounded.
Primary evidence: movement.cpp ToppingOut branch marks completion when the native
climb/vault predicate clears, without checking the existing airborne predicate.
It also reports Grounded on timeout even while falling. The existing Airborne
regrab path does not honor the top-out cooldown.
Sanctioned path: preserve the existing TASK_CLIMB ownership handoff and existing
fall/in-air predicates; do not add guessed native hashes or animation assets.
Execution proof: compile and run the production top-out branch with fake native
readbacks for acceptance, rejection, falling, landing, and timeout sequences.
Player-visible boundary: a real angled-roof mantle still needs in-game acceptance;
this repair must not claim that an unproved lateral animation is finished.


## Local implementation and build

Changed only the relevant transition branches in the existing dirty runtime module.
A completed native task cannot count as a landing while the ped is airborne.
A timeout preserves falling velocity and enters Airborne; that path honors the existing
1800 ms top-out cooldown. No roof teleport, new animation asset or native hash was added.
`tools/verify_rdr2_climb_transitions.py` compiles and executes these exact production
branches with controlled native readbacks; four bad variants fail. Existing #160/#161/
#169 contracts pass. The full development build passed as
2B7269E96665B50992C807F16108F3251073AEA5BC28471D98DEC9B745F0AEA0.
It has NOT been installed. A full source audit found 124 passes, 15 failures, 8 missing
inputs and 2 explicitly omitted unsafe fixtures. Results and individual logs are in
out/rdr2-runtime-audit/. Do not treat the build as whole-runtime acceptance.
Build preparation reconciled the merged #170/#372 road-speed removal, retained legacy
INI values, and corrected stale settings and recurrence-audit gates. The latter's
singular/plural failure-class parser has 14 passing tests. Other dirty runtime work was
preserved. #252 and its sibling climbing issues remain actionable; this does not prove
a real mantle, reliable entry, or an acceptable sideways climbing animation.

2026-09-08 delivery: climbing transition repair is now installed with the minimap lifecycle repair in development ASI 5146B05119144B87F7D1075F60568C353268DFC6586EF0B529F88048E2A7C962, matching game-root bytes. Source transition tests pass; angled roof motion remains unverified. No settings or catalog files were replaced.
