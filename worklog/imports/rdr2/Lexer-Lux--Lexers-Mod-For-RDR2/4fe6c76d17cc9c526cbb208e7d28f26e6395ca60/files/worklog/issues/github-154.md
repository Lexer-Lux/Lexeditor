# GitHub #154 - Shoulder Switch With Gun Holstered

## Recurrence audit before source edits

- **Primary evidence/reference:** live #154 asks one direct question and reports
  one current failure: shoulder switching is still absent with Arthur's gun
  holstered. The coupled #8 body explicitly requires full shoulder movement both
  with and without a drawn weapon. Current source, resolved PAD/native
  definitions, opened Story call sites, and runtime logs are evidence; previous
  promises are not.
- **Sanctioned path:** the issue-owned camera module may own the resolved shoulder
  action and flip only its applied camera side. It must not draw/unholster a
  weapon, synthesize combat state, or fight a second Rockstar shoulder handler.
  Holstered behavior is normal gameplay and is independent of tilde/dev mode.
- **Execution proof:** a bounded edge record must include holstered/armed state,
  current camera profile, old/new side, and applied horizontal value. Idle
  heartbeat must prove the module ran even when no edge occurred. A setter call
  is not proof that the visible camera moved.
- **Rendered/player-visible acceptance:** in third-person free roam, press the
  configured shoulder-switch control once while holstered and see a complete
  left/right swap; press again and see the exact reverse. Repeat armed and while
  aiming. There must be no centering, fractional movement, double flip, forced
  weapon draw, camera teleport, or dependency on developer mode. First-person,
  cinematic, and blocked mission cameras must remain untouched.
- **Per-frame mutation:** only the documented frame-scoped gameplay-camera
  parameter/LOW-state calls may repeat. Shoulder state changes only on a rising
  edge; no per-frame ped weapon, task, holster, or inventory write is allowed.

## Direct answer

Whether holstered switching is possible depends on whether the gameplay-camera
parameter native accepts the same signed horizontal offset outside aim/weapon
states. The module must not claim this from input detection alone. The source
pass will preserve the holstered path if the native contract is general, and
runtime visual acceptance will remain required.

## Repair and direct answer

Yes: the evidence supports a holstered camera-side candidate without drawing a
weapon. `_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` (`0x066167C63111D8CF`) accepts a
general third-person horizontal offset and distance and has no weapon-state
argument (`_downloads/natives.json:10151-10177`). The previous implementation
failed before that native: it depended entirely on the contextual
`INPUT_SWITCH_SHOULDER` action, and the installed camera log had heartbeats but
no shoulder edge for Lexer's holstered X press.

The module now adds a physical X rising edge for that exact reported keyboard
input, keeps the semantic action for armed/remapped/controller contexts, and
merges them before exactly one side reversal. It does not use raw controller
D-pad-left while holstered because authoritative control data shows that same
physical source owns Player Menu and Open Journal outside the shoulder context
(`settings.meta:3766-3769`). Consuming it globally would replace one missing
feature with a controller regression.

The edge record includes `source`, `profile`, `aimHeld`, current `weapon` hash,
resolved `holsterTransition`, `oldSide`, `newSide`, and `appliedHorizontal`.
There is no weapon/task mutation. Static verifiers passed, but this is not
player-visible acceptance: Lexer must still see X move fully between both sides
while holstered, repeat the reverse press, and confirm armed/aim switching has
no double flip, centering, or teleport.

## 2026-08-10 returned-test snap-back correction

Lexer saw the camera begin moving and immediately return. The merged-input
implementation had no cross-source debounce: physical X could produce the raw
keyboard rising edge first, then Rockstar's contextual
`INPUT_SWITCH_SHOULDER` just-pressed edge on a following frame. Both paths
flipped the same persistent side, yielding right->left->right and exactly the
reported brief movement/snap-back.

Physical X now owns that press as one transaction. While X is down, either raw
or mapped detection resolves to the keyboard-X edge and suppresses mapped
shoulder edges for 300 ms. Controller/remapped mapped actions remain unchanged
when physical X is not down. A suppressed second-source edge is logged, and
only the first edge reaches the one side reversal.

The #154, #8 and #128 camera verifiers passed together. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; one stable visible swap per press remains `test me`.

## 2026-08-10 live double-edge correction

The current log proved the previous debounce was still wrong. One physical X
press produced two consecutive accepted transactions: right-to-left, then
left-to-right. The condition returned `KeyboardX` again when the delayed mapped
edge arrived while X remained down.

Only the physical rising edge can now return `KeyboardX`. A mapped edge while X
is still held is discarded, and the time window still rejects a mapped edge
that arrives just after release. The verifier rejects the former combined
condition explicitly.

## 2026-08-11 evidence correction

The latest source still did not implement holstered switching. It observed a
physical X edge and then assumed Rockstar would change the side. Rockstar's
official control documentation limits shoulder switching to the aiming state:
https://support.rockstargames.com/articles/Gz8C860wUX2b8Hin1fxf1/
changing-the-perspective-of-the-third-person-camera-in-red-dead-redemption-2

The local public CAMERA native database has no shoulder-side setter. The one
available continuous control,
`_SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE` (`0x066167C63111D8CF`), exposes speed,
horizontal magnitude, and distance. Live #154/#175 results already showed that
negating its horizontal value does not mirror Arthur across the screen.

The current module therefore preserves X and mapped-action observation plus a
rendered-camera settle readback, but this is a diagnostic, not a completed
holstered switch. It does not synthesize aim, draw a weapon, change tasks, or
claim that an observed X press moved the camera. A faithful holstered switch
still needs an identified engine-side setter/internal hook or a proven camera
data path. It must remain actionable after integration; compiling this
diagnostic does not justify `test me`.
