# #190: Stop untagged hostiles appearing in tagged-only mode

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/190)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #94 worklog](github-190/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-94.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 minimap lifecycle preflight
Failure class: source-only checks previously pinned broken behavior; preserve the 250 ms limit and never spam modifiers. Primary evidence: live issue and retained wolf report; existing verifier read before recon.cpp. Local source already includes animals, but disabling ReconTagging exits before the minimap restore path. Sanctioned path: existing reversible BLIP_MODIFIER_HIDDEN removal and SET_POLICE_RADAR_BLIPS transition, supported by abigail2_1.c and mob2.c. Execution proof: compile and execute production suppression code with controlled native readbacks; require restoration once, re-enable without stale throttle, animal inclusion and no repeated modifiers. Player-visible acceptance: untagged wolves stay hidden; tagged targets show; disabling tagged-only or all Recon restores vanilla markers. No game-visible claim from harness tests.

Implementation: shared release helper restores vanilla police radar and hidden entity modifiers once, resets the sweep deadline, and runs when Recon itself is disabled. Existing animal inclusion and 250 ms modifier limit remain. Production C++ harness passes and rejects four mutations (missing restore, stale deadline, animal exclusion, repeated modifier). Existing marked-only, crash guard and cutscene checks pass. Development build installed and SHA-256 verified: 5146B05119144B87F7D1075F60568C353268DFC6586EF0B529F88048E2A7C962. Only ASI and version manifest copied; no INI/catalog change. Prior 1.6 MB ASI retained under out/rdr2-previous-runtime. In-game wolf visibility and off/on acceptance remain unverified; keep actionable.

## 2026-09-22 misc-fixes diagnostic
Read the suppression sweep fully: 250 ms cadence, per-entity BLIP_MODIFIER_HIDDEN plus police-layer override, tagged blips restored, dead handles pruned, every hide logged. For the wolf-howl case the code cannot distinguish three causes without the log: wolves beyond the 160-ped snapshot cap, disposition not Enemy at howl time, or a script re-enabling the police layer on the howl transition between sweeps.
Human test, needs built ASI on a game machine: enable Tagged Only, trigger the wolf howl, then check GameplayTweaks.log for minimap hid lines naming the wolves. No hid lines means the sweep never classified them (report nearby ped count and timing). Hid lines plus visible dots means the layer is re-enabled after the sweep (report how long dots persist). Report log lines with dot behavior. Issue stays actionable.
