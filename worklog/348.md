# Issue 348 — Belt lantern orientation and visibility

## Requirements
Fix sideways tilt at several attachment points and intermittent
disappearance with the melee belt. Correct orientation and visibility
during movement. Main lantern behavior is #105; leg clipping is #295.
The issue states deferral must not become waiting-on-Lexer.

## Findings (2026-09-22)
- Code: `plugins/rdr2/native_runtime/GameplayTweaks/modules/belt_lantern.cpp`
  (482 lines). Attachment is bone-resolved (PH_Belt_Thrower / bone 2656,
  WEAPON_ATTACH_POINT_LANTERN) with runtime pose calibration
  (`attachBeltLanternCalibrationPose`, best-pose selection with rotation
  scores and attach readback).
- Pose selection is empirical: the right fix is a calibration-data or
  pose-table change driven by in-game observation, not a blind constant
  edit. No compile check is possible here either (build needs the external
  RDR2 SDK).
- Left actionable: needs an in-game session (equip states incl. melee
  belt, movement) to capture calibration logs, then a data-driven fix.

## Next work (agent with game access)
Run the calibration path in-game across belt states, collect the pose
logs, and set the per-state pose from evidence.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
