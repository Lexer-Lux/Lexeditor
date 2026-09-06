# World camera controls

The user confirmed proportional right-stick world-camera rotation works on
2026-09-05. Vertical camera and battle controls remain separate issues329/330.

Canonical implementation: games/ff8/ffnx_modern_controls. The DLL wraps both
complete native camera calls0053FBB4 and0054101C after checking original bytes.
Native right-stick movement/zoom aliases are centered in world mode only.
Raw input is reset on every poll to avoid stale movement after disconnect.

Native camera follow cancels a simple added yaw. After stick movement, preserve
pre-update yaw and add proportional input with fractional remainder. Native
shoulder rotation and state changes retain their normal behavior. Pitch and
movement still run through the original camera routine.

Tests: verify_ff8_modern_controls_compiled_core.py and
verify_ff8_world_camera_native_seam.py. Do not use the retired fixed input hooks.
