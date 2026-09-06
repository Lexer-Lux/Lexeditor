# GitHub #158 — lantern light versus player-body occlusion

## 2026-08-10 recurrence audit before mechanism review

- **Primary evidence/reference:** the live request asks whether only the player
  character can be made transparent to the belt lantern's light so his body
  does not block most of its illumination. Required evidence is the local
  native database/SDK, extracted light and object metadata, decompiled Story
  scripts, and any current module light call. A renderer-sounding native name,
  a light draw call, or a brighter screenshot is not proof of per-light entity
  exclusion.
- **Sanctioned path:** implement only a resolved per-light/per-entity exclusion
  or shadow/occlusion control whose full signature and Rockstar usage are
  opened. Global player invisibility, disabling the player's render/shadows,
  adding a second compensating light, or changing world collision are not
  substitutes for lantern-only body transparency.
- **Execution proof:** if a supported control exists, record the exact light
  owner/handle, player target, one bounded apply transition, authoritative
  readback, release path, and idle heartbeat. If the script-native light has no
  handle or exclusion surface, record the searched primary files and the exact
  limitation; do not add an intent-only call.
- **Player-visible acceptance:** only this belt lantern illuminates through
  Arthur/John while the player and all world geometry remain normally visible
  and shadowing to every other light. Turning the belt light off must restore
  ordinary presentation without residue. Any approximation that merely floods
  both sides of the body does not satisfy the issue.
- **Every issue-owned per-frame native:** no global visibility, shadow, render,
  proof, alpha, collision, or light-parameter setter may fight the engine per
  frame. The existing frame-scoped lantern light draw may remain; an exclusion
  control, if proven, must be transition-applied and released, with bounded
  readback/heartbeat.

## Resolved script-native boundary

No lantern-only player exclusion mechanism exists in the resolved script-native
surface, so no runtime mutation was added.

- `_downloads/natives.json:23732-23772` defines `DRAW_LIGHT_WITH_RANGE` with
  only position, RGB, range, and intensity. It returns no light handle that
  another call could configure.
- Entity-light controls at `:23775-23842` accept only an entity plus color,
  intensity, or type. They expose no excluded target, shadow mask, or player.
- Object-light controls at `:53665-53723` accept the light-bearing object plus
  intensity, translucency, or scattering. They cannot name a second entity to
  exclude, and the current belt glow is a frame-scoped script light rather than
  an addressable object-light handle.
- The only shadow-related natives found are global cascade controls and a
  rope-only shadow toggle. Neither is per-light or per-player. Decompiled Story
  calls to `DRAW_LIGHT_WITH_RANGE` likewise pass only its eight documented
  scalar parameters.

`tools/reverse-engineering/verify_lantern_light_exclusion_issue_158.py` now
locks that evidence boundary: it verifies the exact native signatures and
rejects global player visibility/alpha, cascade-shadow, or unrelated object-
light substitutions in `belt_lantern.cpp`. The verifier passed.

The direct answer is therefore **no supported Story Mode ScriptHook mechanism
was found to make only Arthur/John transparent to only this lantern light**.
Doing so would require a renderer/material hook or custom light/shader path
outside the resolved script-native API. Adding a second light on the far side,
making the player globally transparent, or disabling global shadows would alter
the requested behavior and was deliberately not implemented. This issue remains
actionable for any future renderer-hook evidence; no build, install, or label
change was made.
