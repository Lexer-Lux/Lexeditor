"""Physical shop-display consistency plan contract (#140).

Issue 140 asks for physical shop displays that reflect stock where
possible. Shop inventory and physical displays are separate layers:
shopsinventories controls menu stock while shelves and counters are
authored props plus scripted inspect/buy points, and vanilla already
sells more entries and variants than it physically displays. The viable
scope is representative stock: remove displays for categories no longer
sold and hand-place or bind limited signature items.

This module records that plan shape as checkable data and validates a
display plan: it must name representative layouts with their limits and
must not claim full automatic one-to-one mirroring, which needs a
runtime display manager plus per-interior collision, navmesh, robbery,
mission, and streaming tests. No gameplay claim: the layouts and the
Lexer choice still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Elements a representative-stock plan must contain.
REQUIRED_ELEMENTS = (
    "representative_layouts",
    "stated_limits",
    "category_level_consistency",
    "signature_item_binding",
)

# Per-interior checks a full runtime display manager would still owe.
MANAGER_CHECKS = (
    "collision",
    "navmesh",
    "robbery",
    "mission",
    "streaming",
)

# Claims the issue discussion already rejected.
REJECTED_CLAIMS = (
    "automatic_full_mirroring",
    "one_to_one_shelving",
)


def required_elements() -> list[str]:
    """Return the required representative-stock plan elements."""
    return list(REQUIRED_ELEMENTS)


def manager_checks() -> list[str]:
    """Return the checks a full display manager would still owe."""
    return list(MANAGER_CHECKS)


def validate_display_plan(plan: Mapping) -> list[str]:
    """Check a shop-display plan against the representative scope."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Display plan must be a mapping."]
    claim = str(plan.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim:
            errors.append(f"Plan reuses the rejected claim {rejected}.")
    elements = plan.get("elements") or {}
    for required in REQUIRED_ELEMENTS:
        if elements.get(required) is not True:
            errors.append(f"Plan must include {required}.")
    if "runtime_display_manager" in claim:
        checks = plan.get("manager_checks") or {}
        for required in MANAGER_CHECKS:
            if checks.get(required) is not True:
                errors.append(
                    f"Display manager must still prove {required}."
                )
    return errors


# Fields of one representative layout template. A template binds one shop
# type to its display slots (category-level consistency plus limited
# signature items) and states its limits openly, so the game-side layout
# work has a checkable shape instead of an open brief.
LAYOUT_TEMPLATE_FIELDS = (
    "shop_type",
    "display_slots",
    "category_assignment",
    "signature_items",
    "stated_limits",
)


def layout_template_fields() -> list[str]:
    """Return the fields a representative layout template must carry."""
    return list(LAYOUT_TEMPLATE_FIELDS)


def validate_layout_template(template: Mapping) -> list[str]:
    """Check one representative layout template for completeness."""
    errors: list[str] = []
    if not isinstance(template, Mapping):
        return ["Layout template must be a mapping."]
    for field in LAYOUT_TEMPLATE_FIELDS:
        if not template.get(field):
            errors.append(f"Layout template must state {field}.")
    slots = template.get("display_slots")
    if isinstance(slots, list) and not slots:
        errors.append("Layout template needs at least one display slot.")
    claim = str(template.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim:
            errors.append(
                f"Layout template reuses the rejected claim {rejected}."
            )
    return errors
