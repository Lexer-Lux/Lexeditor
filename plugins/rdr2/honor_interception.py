"""Honor event/tier interception design contract (#161).

Issue 161 needs real per-action honor behavior. The audit side is exact:
21 independent event disable bits and 19 shared hard-coded magnitude
tiers, exposed honestly in the editor (event toggles plus the shared-tier
table with its scope note; per-action amounts stay absent). What is
unproven is intercepting one honor event before its identity is lost,
because the engine applies tier amounts after the event fires. The
bounty-hunter audit adds one concrete target: dispatched PoliceDog
bloodhounds fall through Rockstar's generic farm-animal penalty while
human bounty hunters are already hostile-classified.

This module records the interception design as checkable data and
validates an interception plan: the hook must sit before tier
application, preserve the event identity, block only the bounty-dog
case, and keep the UI honest about shared tiers. No gameplay claim:
the native hook and the game session still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Properties a candidate interception point must prove before any hook
# is presented as the per-action path.
REQUIRED_HOOK_PROPERTIES = (
    "fires_before_tier_application",
    "preserves_event_identity",
    "bounty_dog_only_blocking",
)

# UI honesty rules the editor side already keeps; an interception plan
# must not undo them.
UI_HONESTY_RULES = (
    "no_per_action_amount_fields",
    "shared_tier_scope_note_kept",
)

# Proposals the issue discussion already rejected.
REJECTED_APPROACHES = (
    "post_tier_amount_rewrite",
    "independent_amount_fields_without_hook",
)


def required_hook_properties() -> list[str]:
    """Return the properties an interception point must prove."""
    return list(REQUIRED_HOOK_PROPERTIES)


def validate_interception_plan(plan: Mapping) -> list[str]:
    """Check an honor-interception plan against the design contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Interception plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected} "
                "position."
            )
    hook = plan.get("hook") or {}
    for required in REQUIRED_HOOK_PROPERTIES:
        if hook.get(required) is not True:
            errors.append(
                f"Interception point must prove {required}."
            )
    ui = plan.get("ui") or {}
    for rule in UI_HONESTY_RULES:
        if ui.get(rule) is not True:
            errors.append(
                f"Editor UI must keep {rule} until a hook is proven."
            )
    return errors
