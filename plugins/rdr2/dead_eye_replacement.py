"""Dead Eye replacement protocol: kill gains out, core regeneration in (#227).

Issue 227 asks to remove kill-based Dead Eye gains and replace them with
core regeneration. Adding regeneration while keeping the gains would only be
a partial substitute, and neither a decompiled native annotation nor a
per-frame negative refill correction proves the kill-gain source on its own.
This module records the ordered proof protocol as checkable data and
validates a replacement plan: the kill-gain source must be resolved first,
selective suppression must be shown by a disposable causal comparison next,
and only then may core-scaled regeneration integrate with the existing
consumption/reserve state. No engine hook is invented here and no gameplay
claim is made; the comparison and the game session are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Step 2 comparison coverage: every one of these situations must be measured
# at baseline multiplier 1 and candidate multiplier 0, with meter readings
# before and after, and the previous multiplier restored afterwards.
COMPARISON_SITUATIONS = (
    "body_kill",
    "headshot_kill",
    "consumable_refill",
    "mission_refill",
    "active_dead_eye_drain",
    "eagle_eye",
)

PROTOCOL_STEPS = (
    {
        "id": "resolve_kill_gain_source",
        "description": "Resolve the actual kill-gain source; annotations and "
        "per-frame corrections alone do not prove it.",
    },
    {
        "id": "causal_suppression_comparison",
        "description": "Disposable baseline-1/candidate-0 comparison over every "
        "required situation with meter before/after and multiplier restored.",
    },
    {
        "id": "core_scaled_regeneration",
        "description": "Integrate core-scaled regeneration with consumption/reserve "
        "state only after selective suppression is shown.",
    },
)


def protocol() -> list[dict]:
    """Return a deep copy of the ordered replacement protocol."""
    return copy.deepcopy(list(PROTOCOL_STEPS))


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_replacement(plan: Mapping) -> list[str]:
    """Check a Dead Eye replacement plan; empty list means valid."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["plan must be a mapping"]
    if plan.get("keeps_kill_gains"):
        errors.append(
            "plan must remove kill-based gains; keeping them with added "
            "regeneration is only a partial substitute"
        )
    source = plan.get("kill_gain_source")
    if not _non_empty_string(source):
        errors.append("kill_gain_source must name the resolved engine source")
    comparison = plan.get("comparison")
    if not isinstance(comparison, Mapping):
        errors.append("comparison must record the causal suppression comparison")
    else:
        covered = comparison.get("situations")
        if not isinstance(covered, list):
            errors.append("comparison.situations must list the measured situations")
        else:
            for required in COMPARISON_SITUATIONS:
                if required not in covered:
                    errors.append(f"comparison must measure {required}")
        if comparison.get("baseline") != 1 or comparison.get("candidate") != 0:
            errors.append("comparison must run baseline multiplier 1 against candidate 0")
        if not comparison.get("multiplier_restored"):
            errors.append("comparison must restore the previous multiplier afterwards")
    regen = plan.get("regeneration")
    if not isinstance(regen, Mapping):
        errors.append("regeneration must describe the core-scaled integration")
    else:
        if regen.get("core_empty_yield", 1) != 0:
            errors.append("regeneration must yield nothing when cores are empty")
        for preserved in ("item_restoration", "mission_restoration", "permanent_progression"):
            if not regen.get(preserved):
                errors.append(f"regeneration must preserve {preserved}")
    unknowns = plan.get("open_unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("open_unknowns must state what is still unproven")
    return errors


def is_valid(plan: Mapping) -> bool:
    """Return True when the replacement plan passes every structural check."""
    return not validate_replacement(plan)
