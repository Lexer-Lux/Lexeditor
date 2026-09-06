# GitHub #19 — Stealth/Detection Indicators

## Implementation handoff

Added `GameplayTweaks/modules/stealth_indicators.cpp` as an unregistered topic
module. It deliberately does not invent the universal detection percentage that
#13 proved RDR2 does not expose.

The indicator has three discrete evidence-backed states:

- ivory: a hostile ped is focused on the player, `CAN_PED_SEE_ENTITY`
  affirmatively reports visibility, and entity LOS is clear;
- amber: targeted suspicion/agitation exists, or a focused ped is responding to
  a threat;
- red: the ped is in combat with the player.

The indicator is a small directional ring on a shallow arc around the aiming
area, using vanilla `blips/blip_overlay_ring`. It is capped at four, prioritizes
alert state then distance, hides in pause/satchel/death/fade contexts, ignores
ordinary civilians merely glancing at a crouched player, and fades for 500 ms
after a 350 ms hold to prevent flicker. The fade is UI presentation, not an
awareness value.

### Integration

1. Include `modules/stealth_indicators.cpp` with the other topic modules in
   `GameplayTweaks/script.cpp`.
2. In the per-frame block, call
   `updateStealthDetectionIndicators(ped, now, dead || SCREEN_FADED_OUT());`
   when `ped` exists, beside the recon/HUD updates.
3. Rebuild the generated knowledge indexes, build the combined ASI once, install
   it once, hash-verify it, then move #19 from `actionable` to `test me`.

### In-game acceptance

- Crouch or use stealth movement near an unaware hostile: no indicator appears
  merely because the hostile is nearby.
- Enter that hostile's focused, unobstructed view: a subtle ivory directional
  ring appears.
- Trigger suspicion/threat response: the ring becomes amber; combat makes it
  red.
- Break LOS: it holds briefly, fades smoothly, and disappears rather than
  claiming a numeric decay in AI awareness.
- In a crowded town, ordinary civilians do not create indicator clutter.
- Pause/satchel/death/fade screens contain no indicators; no more than four are
  visible around a hostile camp.

### Static evidence

- `codex/stealth-perception.md` requires indicators to use awareness state,
  visibility, distance, and LOS, and forbids treating distance as awareness.
- `_downloads/natives.json` documents `IS_TARGET_PED_IN_PERCEPTION_AREA` as true
  when the observer is focused and looking at the target, and documents
  `CAN_PED_SEE_ENTITY` return 1 as can-target versus 2 not-sure-yet.
- `StealthProbe/script.cpp` supplies the already-audited hashes and signatures
  for perception, targeted motivation, LOS, and combat state.
- `GameplayTweaks/modules/recon.cpp` verifies `blips/blip_overlay_ring` as a
  resident vanilla texture already used successfully by the mod.
- The vanilla `UITUTORIAL` surface exposes only getters for whether its radar
  threat indicator is capable/shown or on. It provides no setter and no per-ped
  awareness feed, so it cannot implement #19 by itself.

No build, install, GitHub mutation, shared dispatcher edit, or generated-index
edit was performed by the feature agent.
# Audit completion and integration

Lexer completed the controlled-observer probe and issue #13 now contains the
stealth-system audit. The audit established that RDR2 is a hybrid rather than a
single MGSV-style meter: sight is a conditional/time-gated state machine,
witness suspicion has its own accumulation/decay, combat can trigger separately,
and animals use separate states. Issue #13's blocker relationship was removed
from #19 after that dependency was completed.

The preserved module was then corrected and registered in the combined script.
Stance and locomotion no longer gate whether the HUD exists; crouch, stealth
movement, walking, running, and sprinting already influence the game's own
perception/noise outcome. The indicator observes that outcome instead of
inventing a second model. Player-targeted aiming plus an observer's actual flee
state now supplies an amber threat response, alongside targeted suspicion and
agitation. Combat remains red. Ordinary focused civilian glances remain filtered
unless there is real targeted awareness or threat response.

`tools/reverse-engineering/verify_stealth_indicators_issue_19.py` checks module
registration, perception/visibility/LOS evidence, suspicion/agitation, targeted
aim/flee response, combat, human/distance/display caps, UI suppression, and the
absence of stance gating or fabricated percentage fields.

This implementation is local and statically verified only. It has not been
built or installed, so #19 remains `actionable`.
