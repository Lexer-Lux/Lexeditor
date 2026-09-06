# GitHub #169 - sliding takeover and surface orientation

## Recurrence audit

- Read `fuckups.txt` before editing. A transition log proves that code ran; it
  does not prove that the visible slide, position, or pose was correct.
- The repair uses only the resolved native slide predicate already in the
  module and `GET_ENTITY_ROTATION` / `SET_ENTITY_ROTATION` from
  `_downloads/RDR2_SDK/SDK/inc/natives.h:1288,1502`.
- The player-visible boundary is no slide-to-climb teleport and a body that
  visibly follows the contacted surface. Static checks and numeric rotation
  readbacks cannot establish that visual result.

## Live evidence and cause

The unified live log captured the reported sequence at process ages
2,329,156-2,334,640 ms. Rockstar entered its native slide before climbing took
ownership. The module then logged five automatic transitions: four
`vanilla_sliding` grabs and one `detected_slipping` grab. One automatic grab
occurred after a previous climb exited for low stamina while the same physical
slide continued.

The source cleared `g_climbSlideStartedAt` in `attachClimbPhysics` and cleared
the whole prequalification latch whenever Rockstar's private slide flag was
false. The live predicate flickered during one physical slide. A later true
frame therefore started a new episode from a contact found after the slide had
already begun. The code called that contact "prequalified" and gave it
coordinate ownership. This produced the late slide-to-climb teleport.

The old orientation path did call `SET_ENTITY_ROTATION`, but it had no readback.
It also treated every frame in the first 80 ms as a new attachment and repeated
the setter during that window. The existing climbing trace showed owned
position (`anchor` equals `actual`), but it could not show whether pitch stayed
applied. The root fit uses the surface contact and two hand-bone clearance
samples. It is not a four-limb IK solver and does not sample either foot. A
claim that every hand and foothold individually drove the pose was not true.

## Repair

- One physical slide is now one 500 ms-debounced episode. A one-frame false
  predicate cannot re-arm it.
- An episode can arm only while the custom state is Grounded. It copies the
  exact contact that existed before the first native-slide frame.
- Native-slide takeover is limited to the same update that first observes the
  slide and requires the current face to match the copied contact within 0.20
  m and a 0.97 normal dot product. It attaches to the copied contact, never a
  later probe result.
- Inferred slipping is disabled while the same native-slide episode is active,
  so a predicate flicker cannot enter through a second automatic path.
- Orientation is written once per attachment instead of once per frame for 80
  ms. The trace records both the immediate `GET_ENTITY_ROTATION` result and a
  second readback after 180 ms, with pitch/yaw errors and an explicit matched
  result. This proves native acceptance and retention only; it does not prove
  the animation looks correct.

## Static and runtime boundary

`verify_climbing_issue_169.py` passed all 14 episode, copied-contact,
same-face, inferred-slip, one-shot orientation, and readback guards. The #97,
#113, #119, #159, #160, #161, #165, #166, #167, prone/climb parity, #9 prone,
#68 safe weapon bridge, and #6 dodge checks also passed. `git diff --check`
reported no whitespace error; it printed only the checkout's CRLF warning.

No build, install, GitHub mutation, commit, or push was performed here. In-game
acceptance still requires a slope that previously reproduced the fault. A
native slide with no proven pre-slide contact must remain wholly native; it must
not turn into climbing later. If the mod takes ownership at slide onset, the
trace must show the copied pre-slide face and both orientation readbacks, and
Arthur must not snap to open air or remain visibly upright against an inclined
surface.

## 2026-08-11 latest returned result

Lexer's latest report, "Sliding still exists," rejects the last paragraph's
native-slide fallback as accepted behavior. The current repair prevents the
late teleport and audits surface rotation, but it explicitly preserves every
native slide that did not have a verified face before the first sliding frame.
It therefore cannot complete the live issue as written.

The current unified trace also shows why the existing automatic conversion did
not engage in the later session: Arthur reached about 6.7 m/s while pushing
forward, but `_IS_PED_SLIDING` stayed false and the resolved cache normal was
approximately horizontal (`normal.z` near zero), so neither the native-slide
episode nor the sloped-contact loss-of-footing path qualified. No automatic
climb state was entered in that trace.

Story scripts use `_IS_PED_SLIDING` only as a read-side restriction. The SDK and
Story corpus contain no resolved native that disables the slide task globally.
The only named `BLOCKED_SLIDING_VOLUME` in `winter2.c:39725` is a mission volume
name; that call site does not establish a reusable player-slide control.
Inventing a per-frame velocity, coordinate, task-clear, or global volume writer
would repeat the engine-fighting failure class in `fuckups.txt`.

No new #169 runtime mutation was added in this pass. The copied-contact and
orientation-retention verifier still passes 14 guards, but #169 remains
actionable: eliminating the unflagged physical slide requires a proven engine
control or a separately specified ground-plane traversal owner. Static success
on the teleport guard is not acceptance of "no sliding."
