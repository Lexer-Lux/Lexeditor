# GitHub #102 — Toxic damages the Health bar

## 2026-08-06 poisoning presentation follow-up

The live issue and latest feedback require Toxic to remain an outer-Health-bar
condition, but not present as only an occasional skull on the Health icon. The
existing integration already owns persistence, `SA_POISONED`, cures, status icon
5, and `drainHealthBarByMinutes`; this feature module does not duplicate or
replace any of those mechanics and contains no Health Core access.

Story asset evidence supports two presentation pieces:

- Rockstar ships the named AnimPostFX `MP_MoonshineToxic` (and a Dark variant).
  The ordinary effect is used as a 4.5-second screen pulse at onset and every 30
  seconds by default, then explicitly stopped when Toxic clears.
- The shipped animation index contains Arthur's dedicated sickness fidgets at
  `mech_loco_m@character@arthur@fidgets@sick@normal@unarmed@big_cough`, with
  clips `sick_a`, `sick_b`, and `sick_c`. One is played 1.5 seconds after onset
  and every 90 seconds by default.

The fidget is limited to model `PLAYER_ZERO` because the evidence is explicitly
Arthur-specific. It is secondary/upper-body playback and is deferred while
aiming, fighting, mounted, in a vehicle, falling, ragdolled, or dead. A vomiting
scenario was deliberately not forced: the shipped ambient vomit assets exist,
but no Story evidence identifies one as Arthur's Toxic reaction, and a scenario
would seize locomotion during combat.

The module reads two optional settings directly, so integration does not need
shared globals:

```ini
[Toxicity]
PresentationPulseSeconds=30
PresentationFidgetSeconds=90
```

Integration owns including `modules/toxic_presentation.cpp`, calling
`updateToxicPresentation(ped, now)` once per live gameplay update after
`updateToxicInteraction(ped)`, and calling `stopToxicPresentation()` during
script shutdown/forced cleanup so a running owned post-FX cannot survive unload.
The call should still run when Toxic is disabled or cured so it can stop its
owned effect.

`verify_toxic_presentation_issue_102.py` checks the exact post-FX and Arthur
animation assets, the safe-state gates, both settings, cure cleanup, and the
absence of core/drain ownership. No build, install, or runtime test was performed
by the feature agent. Runtime acceptance still requires full/partial Health,
combat deferral, sleep, save/reload, lethal zero Health, no Health Core loss,
visible screen pulses, Arthur fidgets, and immediate presentation cleanup after
a configured Health Cure.

## Ranked outer-bar correction

The prior drain assumed a fixed 100-point outer Health bar. Ranked players have
a larger native outer capacity, so the configured one-hour drain barely moved
the rendered bar. Toxic now drains `GET_ENTITY_MAX_HEALTH(ped, false) - 100`
over the configured duration while leaving the reserved core span untouched.

## 2026-08-10 real-time drain correction

The installed in-game-hour drain was too slow and natural Health regeneration
could offset it. The drain now reads `HealthBarDrainPointsPerSecond`, accumulates
actual entity-health points from real elapsed milliseconds, and clamps at the
100-point boundary reserved for the Health core. While Toxic is active the
player's current Health recharge multiplier is captured, forced to zero, and
restored when Toxic clears. The old `HealthBarDrainHours` path was removed.

Static checks cover the real-time setting, regeneration suppression/restoration,
outer-bar floor, and removal of the old in-game-clock drain. Runtime acceptance
still requires confirming the configured points per second and cure restoration.
