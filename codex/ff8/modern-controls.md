# World camera controls

The user confirmed proportional right-stick world-camera rotation works on
2026-09-05. Vertical camera and battle controls remain separate issues329/330.

Canonical implementation: plugins/ff8/ffnx_modern_controls. The DLL wraps both
complete native camera calls0053FBB4 and0054101C after checking original bytes.
Native right-stick movement/zoom aliases are centered in world mode only.
Raw input is reset on every poll to avoid stale movement after disconnect.

Native camera follow cancels a simple added yaw. After stick movement, preserve
pre-update yaw and add proportional input with fractional remainder. Native
shoulder rotation and state changes retain their normal behavior. Pitch and
movement still run through the original camera routine.

Tests: verify_ff8_modern_controls_compiled_core.py and
verify_ff8_world_camera_native_seam.py. Do not use the retired fixed input hooks.

## Vehicle throttle

In the supported English executable (SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`),
world input at `0x557477` reads rY at `0x020409A4`. It ignores magnitudes through
45 and stores signed drive `127-rY` in the input record's byte `+0xB`.
The physics routine at `0x557E14` divides that drive by 48 for cars, 16 for
Garden, or 8 for Ragnarok, then adds the integer quotient to the current speed
at `0x020409E8`. Changing axis magnitude alone therefore changes acceleration,
but repeated input still reaches the same final speed.

The signed clamp at `0x55801D` uses ESI as its positive limit, after native
terrain and turning adjustments. Its first six bytes set EAX to the negative
limit and compare EDX against it; execution continues at `0x558023`. Neutral
input instead takes the existing friction/coasting path at `0x558031`.
The focused `verify_ff8_vehicle_cap_binary.py --exe <path>` check confirms the
guarded instructions against that executable and executes both clamp branches
for reduced limits and positive/negative speeds without changing game files.
