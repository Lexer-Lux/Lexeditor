# #104: Animated binocular quick access

[Live request and comments](https://github.com/Lexer-Lux/Lexeditor/issues/104)

## Scope

Hold Cover to draw and stow binoculars with normal animations. A short tap keeps native cover behavior. Preserve the accepted ability to move during draw and stow; raised locomotion and put-away prompt behavior still need rendered acceptance. The live #357 request records merged pointer safeguards, but repeated binocular entry is still needed to assess the reported crash. This repair does not claim that crash is solved.

## 2026-09-08 stow completion repair

`C:/RDR2Mod/GameplayTweaks/modules/combat_inventory.cpp` previously ended stow ownership at its configured timer even if the native swap task was still running. A hold queued during the return could then begin retrieval over an unfinished stow.

The timer is now a minimum. Completion also requires the known swap task (`716706914`) to leave queued/running states 0/1 and the exact authored `mech_inventory@binoculars` / `hold_2_exit` clip to stop. The clip check is independent of the speed setting, so default rate 1 also receives the completion guard. These are the existing primary-source task/clip identities checked by the quick-access and transition verifiers.

If either remains active five seconds beyond the minimum window, the code cancels deferred input and enters an inert recovery state. It does not clear tasks, teleport, equip another weapon or announce completion. Recovery yields controls and continues to check task/clip state. A held key, a release/repress while the old task remains active, and a press held through recovery cannot start retrieval. After the old task and clip stop, a physical release is required before a fresh hold. Disabled/dead/fade/menu cleanup also clears stow/recovery state.

## Validation

`tools/verify_rdr2_binocular_stow.py --runtime-root C:/RDR2Mod` compiles the actual production completion helper, stow branch, recovery branch and dismissal latch. Production passes; four mutants are rejected. Tests cover the minimum window, queued/running slow tasks, an exit clip that outlasts the task, deferred entry after real completion, timeout, repeated input while the old task remains active, held input through recovery, new input after release and clock rollover. Compiler files are temporary and removed.

Existing `verify_binocular_quick_access_issue_4.py` and `verify_binocular_transition_probe_issue_84.py` pass. No prompt-registry logic, movement bridge or camera mask was changed. Parent owns build/delivery. No game files were changed while #151 owns the installation.

## Next work

Keep the full issue actionable until delivery and rendered checks are prepared. After #357 candidate delivery, repeat draw/stow in free roam and include a hold started during a slow stow. It must not cut the return animation short or start a conflicting draw. Verify normal tap cover, raised movement, prompt suppression and repeated scope entry without a crash. Source tests establish branch behavior only, not native timing, animation appearance or crash acceptance.

Combined development build passed: 334A268547E779406A80C5865FD4463DEE8E80FF2BF5FA3E4D352FBD88C22342. Candidate: out/rdr2-after-duration/GameplayTweaks.asi, matching release manifest. Not installed: duration experiment #151 remains active. Build log: out/rdr2-build-overflow-binoculars.log. Agent-side module tests passed; game acceptance remains open.

