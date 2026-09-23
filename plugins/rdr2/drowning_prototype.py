"""Controlled drowning-presentation prototype definition (#171).

Issue 171 requires a readable struggle/submerge transition at zero
swimming stamina with death still inevitable: no rescue window, no HUD
warning. The zero-second and trough-animation proposals stay rejected,
and the engine-owned drowning-time experiment is still unbuilt.

This module records the agreed prototype shape as checkable data and
validates a prototype plan: it must latch an irreversible terminal state
at zero stamina, attempt a short engine-owned presentation, keep death
inevitable, and fall straight through to immediate death wherever the
presentation cannot safely take control. No gameplay claim: building the
prototype and its recovery checks still needs the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Elements the agreed prototype shape requires.
REQUIRED_ELEMENTS = (
    "irreversible_latch_at_zero_stamina",
    "controls_disabled",
    "short_struggle_submerge_presentation",
    "no_rescue_window",
    "no_hud_warning",
    "unchanged_death_aftermath",
)

# Conditions under which the plan must skip the presentation and use the
# unchanged immediate death instead.
FALL_THROUGH_CONDITIONS = (
    "shallow_water",
    "ragdoll",
    "unsafe_first_person",
    "mission_forbids_takeover",
    "clip_refused_control",
)

# Proposals the issue discussion already rejected.
REJECTED_APPROACHES = (
    "zero_second",
    "trough_animation",
)


def required_elements() -> list[str]:
    """Return the required prototype elements."""
    return list(REQUIRED_ELEMENTS)


def fall_through_conditions() -> list[str]:
    """Return the conditions that force immediate death."""
    return list(FALL_THROUGH_CONDITIONS)


def validate_drowning_plan(plan: Mapping) -> list[str]:
    """Check a drowning-prototype plan against the agreed shape."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Drowning plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected} proposal."
            )
    elements = plan.get("elements") or {}
    for required in REQUIRED_ELEMENTS:
        if elements.get(required) is not True:
            errors.append(
                f"Prototype must include {required}."
            )
    fall_through = plan.get("fall_through") or {}
    for condition in FALL_THROUGH_CONDITIONS:
        if fall_through.get(condition) != "immediate_death":
            errors.append(
                f"Condition {condition} must fall through to immediate death."
            )
    if not plan.get("recovery_checks"):
        errors.append(
            "Prototype must list recovery checks before any drowning test."
        )
    return errors
