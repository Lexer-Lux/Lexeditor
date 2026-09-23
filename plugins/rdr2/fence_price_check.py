"""Fence Honor pricing purchase-comparison contract (#204).

Issue 204 requires fences to reward low Honor with better prices and
penalize high Honor while normal stores keep their usual curve. The last
low-Honor attempt still showed baseline prices, so no new purchase
comparison is valid until its legs are pinned down.

This module records that comparison contract as checkable data and
validates a purchase-comparison plan: a named fence shop and item, a
low-Honor leg and a high-Honor leg under the same item/shop controls,
readable before/after prices, and ownership of the still-unbuilt
independent shop-modifier correction. No gameplay claim: the correction
and the game session are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping

# Legs a valid comparison must contain.
REQUIRED_LEGS = ("low_honor", "high_honor")

# Controls that must match across legs for the comparison to mean anything.
MATCHED_CONTROLS = ("shop", "item")


def validate_price_check(plan: Mapping) -> list[str]:
    """Check a fence-pricing purchase comparison against the contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Price check must be a mapping of comparison legs."]
    legs = plan.get("legs")
    if not isinstance(legs, Mapping):
        return ["Price check must map each required leg to its observation."]
    for required in REQUIRED_LEGS:
        if required not in legs:
            errors.append(f"Comparison must include a {required} leg.")
    present = [legs[name] for name in REQUIRED_LEGS if name in legs]
    for name, leg in zip(REQUIRED_LEGS, present):
        if not isinstance(leg, Mapping):
            errors.append(f"Leg {name} must be a mapping.")
            continue
        for control in MATCHED_CONTROLS:
            if not leg.get(control):
                errors.append(f"Leg {name} must name {control}.")
        if leg.get("price") is None:
            errors.append(f"Leg {name} must record a readable price.")
    values = {
        control: {leg.get(control) for leg in present if isinstance(leg, Mapping)}
        for control in MATCHED_CONTROLS
    }
    for control, seen in values.items():
        if len(seen) > 1:
            errors.append(
                f"Legs must share the same {control}; comparison across "
                "different shops or items proves nothing."
            )
    if plan.get("shop_kind") != "fence":
        errors.append(
            "Comparison must run at a fence; normal stores keep their "
            "usual Honor curve and cannot prove the fence correction."
        )
    unknowns = " ".join(str(item) for item in (plan.get("open_unknowns") or [])).lower()
    if "shop-modifier" not in unknowns and "shop modifier" not in unknowns:
        errors.append(
            "Plan must own the unbuilt independent shop-modifier correction "
            "as an open unknown instead of assuming it installed."
        )
    return errors
