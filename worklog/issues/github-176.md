# #176: Finish exhaustion handling without consuming cores

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/176)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

- [Original Lexer-Lux/Lexers-Mod-For-RDR2 #78 worklog](github-176/imports/Lexer-Lux--Lexers-Mod-For-RDR2/4fe6c76d17cc9c526cbb208e7d28f26e6395ca60/github-78.md) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.

## 2026-09-08 horse recovery source candidate

Read live #176 body/full comments and the original horse report. The reported gap is automatic slowdown: empty horse stamina protects its core but holds a gait that does not regenerate until the rider presses Ctrl. The current script guard only disables sprint/jump, pins the core and clamps a negative movement rate to zero. It does not lower the horse's already selected gait.

Recurrence audit: reviewed `C:/RDR2Mod/fuckups.txt`, the Dead Eye verifier, and central runtime-engine limits. Relevant failure classes: a control disable does not undo an already selected action; setter calls do not prove motion; resource restoration must not mutate progression/maxima. Primary evidence: 1491.50 `act_cajav_homerob1::func_261/599` applies mounted walking blend1; `act_hunting_2` uses `TASK::SET_PED_DESIRED_MOVE_BLEND_RATIO(mount,0)` on the actual mount during dismount; the SDK supplies the desired-gait setter/getter. The combination supports a candidate request to lower an exhausted mount to walking; acceptance still requires its actual mounted response.

New `GameplayTweaks/modules/horse_exhaustion_recovery.cpp` receives the existing exhausted-mount latch. At most ten checks/commands per second, it requests walking only if the mount currently requests a higher gait. Stopped/slower horses stay stopped/slower. Rider/mount identity, existence, death, ragdoll, swimming, jumping and falling gates prevent unrelated changes. It never installs a persistent maximum-speed cap, replays Ctrl, clears tasks, or writes stamina/cores. The existing controller remains the resource owner. Measured desired gait before/after, actual speed, stamina and configured movement rate appear in a bounded diagnostic; idle and suspended paths have separate records. A failed native setter can report unchanged desired gait, rather than masquerading as recovery.

`tools/verify_rdr2_horse_exhaustion.py --runtime-root C:/RDR2Mod` compiles the production helper with a controlled native boundary. Exhausted/healthy, stopped/walking/running, cadence, mount switch, dead/ragdoll/swim/jump/fall gates, invalid desired values and failed-setter readback pass. Six regressions are rejected. This proves command ownership and scheduling, not real horse deceleration or bar recovery.

Root integration: include the helper after movement.cpp, then call `updateHorseExhaustionRecovery(rider, mount, mountStaminaEmpty, now)` immediately after the existing mountStaminaEmpty calculation; call with no mount/false when that path has no horse. The upstream gate already excludes locked/disabled reserve handling. No script.cpp or game-directory edits were made by this agent. Build and delivery remain with root; do not alter #151's active experiment files.

Required acceptance after a delivered candidate: use a healthy ridden horse on level dry ground with positive walking recovery. Exhaust the outer stamina ring while keeping the usual riding input; it should slow without Ctrl and the outer bar should begin recovering without consuming the core. Release sprint and allow the existing 18% native-meter threshold to clear the latch, then accelerate normally. Check stopping, dismounting, horse switching, jumping and entering water. Report the horse-recovery diagnostic alongside the existing stamina trace if desired gait changes but actual speed or regeneration does not. Dead Eye/Eagle Eye behavior is unchanged and remains part of full issue acceptance.

Root integrated and built this source with the independent Recon radii. Development build passed, ASI SHA-256 `8AE9385498F96437AFB504381F6B8E34491E3A740D8993C539D89C21B3D7BB2E`. The small candidate is held under `out/rdr2-after-duration`; it is not installed because #151 remains active. No game acceptance is claimed.
