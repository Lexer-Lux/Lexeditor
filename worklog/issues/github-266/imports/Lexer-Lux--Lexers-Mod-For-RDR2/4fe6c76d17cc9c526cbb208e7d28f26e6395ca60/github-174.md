# GitHub #174 - Camera Distance Heavily Clamped

## Recurrence audit before source edits

- **Primary evidence:** the live issue reports that horizontal calibration was
  released from its narrow limit while distance still stops at an artificial
  boundary. The current camera source clamps every profile distance to
  `0.30..8.0` both on load and during keypad editing. The resolved
  `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` native names the value only as
  `distance` and documents no numeric maximum.
- **Sanctioned path:** retain finite, nonnegative distance validation and pass
  the configured value to the existing frame-scoped camera native. Do not
  replace the undocumented 8.0 limit with another guessed upper limit.
- **Execution proof:** the calibration display and saved INI value must continue
  to show the actual submitted distance. Static source checks prove only that
  the artificial cap is absent.
- **Player-visible acceptance:** hold the distance-increase key beyond 8.0 and
  confirm that the camera continues moving and that the saved value reloads.
  First-person, cinematic, and mission camera exclusions must remain intact.
- **Cadence:** only the existing documented frame-scoped camera submission may
  repeat. File writes remain limited to the explicit save edge.

## Source repair

Both copies of the `0.30..8.0` distance clamp were removed. Distance now has no
project-authored upper limit. A non-finite or negative value is reset to zero,
because distance cannot be negative; every other finite value reaches the
existing camera native unchanged. The explicit Numpad-5 save path still writes
the displayed value to the matching profile key.

`tools/reverse-engineering/verify_camera_distance_issue_174.py` checks the
resolved native contract, rejects the old 8.0 cap, and verifies that the saved
profile value is the value submitted to the frame-scoped camera path. Visible
movement beyond 8.0 still requires the combined build and in-game test.
