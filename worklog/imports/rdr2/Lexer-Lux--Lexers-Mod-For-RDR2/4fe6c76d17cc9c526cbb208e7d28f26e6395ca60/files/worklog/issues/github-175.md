# GitHub #175 - Shoulder Switch Still Messed Up

## Recurrence audit before source edits

- **Primary evidence:** the live issue reports that X while aiming alternates
  between a left-side camera and a centered camera. The installed unified log
  proves that each physical X edge reaches the camera module and alternates the
  submitted Aim horizontal value between `+2.95` and `-2.95`. Therefore the
  defect is downstream of input detection and upstream of visible placement;
  another key debounce cannot repair it.
- **Sanctioned path:** use the documented frame-scoped gameplay-camera
  parameter native and real rendered-camera coordinates. Do not mutate weapons,
  tasks, aim state, or invent an unverified shoulder native.
- **Execution proof:** bounded edge/settle records must include the requested
  side, submitted horizontal value, and the rendered camera's measured lateral
  position relative to the player. A submitted parameter is not a visible
  postcondition.
- **Player-visible acceptance:** each X press while aiming must settle on the
  opposite side of Arthur, not in the center, and the next press must return.
  Repeat while holstered and crouched. No double flip, camera teleport, weapon
  draw, or aim-distance flash is acceptable.
- **Cadence:** the existing camera parameter call is documented as per-frame.
  Shoulder state changes only on a rising edge; readback sampling must be
  bounded.

## Source repair

The failed path treated shoulder switching as two opposite numeric offsets and
disabled Rockstar's real aim shoulder action. The live log proves this submitted
`+2.95` and `-2.95` but the screen produced left and centre, so the numeric sign
was not an equivalent replacement for Rockstar's internal aim-camera side.

During standing or crouched aim, the module now leaves
`INPUT_SWITCH_SHOULDER` enabled and lets Rockstar own the side change. On the
rising edge it temporarily stops asserting only the custom horizontal offset
for 500 ms, then resumes the configured Aim or Crouched Aim offset against the
new native side. The holstered physical-X fallback remains module-owned because
Rockstar has no active shoulder context there.

At 650 ms the module projects the final rendered camera coordinate onto the
camera-right vector relative to Arthur and logs the lateral value before and
after the transition, including whether it crossed sides or remained centred.
This is a real camera-position readback, but it is not a substitute for Lexer's
visible acceptance. The combined build must still show left-to-right and
right-to-left aim transitions without centering.

## 2026-08-11 discontinuity correction

The prior 500 ms release window was itself the late jump Lexer described: it
stopped the custom offset during Rockstar's blend, then reasserted it near the
end. That window is removed. Aim switching now leaves Rockstar's mapped action
enabled and submits one constant, nonnegative configured magnitude throughout
the transition. The module does not own or negate a shoulder side.

The 650 ms rendered-coordinate readback remains and classifies the result as a
side crossing, centre collapse, ignored press, or partial movement. Static
checks prove that the old discontinuity and module-owned side are absent; only
an in-game left/right aiming test can prove that the visible result is now
symmetrical and smooth.
