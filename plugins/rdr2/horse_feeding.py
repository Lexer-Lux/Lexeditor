"""Configurable horse feeding and bonding mapping (#134).

Issue 134 allows chosen feed items with a configured bond amount,
integrated with actual feeding. The 1491.50 player_horse source maps
the real path (codex/rdr2/horse-feeding.md): food processing runs
func_433 -> func_739 -> func_454 -> func_758/func_760 -> func_677, event
13/14/15 awards carry base values 15/5/1 while sugarcube/peppermint/
bulrush/mace use event16 with base 5, and eight herbs skip bonding.
Eligibility is the 45-ID func_724 allowlist; preferred selection is the
func_789 ordering of 11 ordinary feeds then 26 herbs. The constant 20
is func_962 on a separate state path that func_739 never calls.

This module records the item-aware mapping shape as checkable data: keep
the item hash through func_739, substitute only the configured magnitude
inside func_454's rank/event-cap/motivation checks, and extend func_724
plus func_789. It rejects the removed after-consumption watcher, fixed
amounts, and generic attribute hooks. No gameplay claim: validating the
dispatcher hook and the per-item configuration still needs the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Native bond award base values from the mapped feeding path.
BOND_EVENT_BASES = {
    "event13": 15,
    "event14": 5,
    "event15": 1,
    "event16": 5,
}

# Script surfaces the mapping must integrate with.
REQUIRED_SURFACES = (
    "func_739_item_identity",
    "func_454_checks",
    "func_724_eligibility",
    "func_789_preferred_selection",
)

# Approaches the issue discussion already rejected.
REJECTED_APPROACHES = (
    "after_consumption_watcher",
    "fixed_amount_substitution",
    "generic_attribute_hook",
)


def bond_event_bases() -> dict[str, int]:
    """Return the native bond award base values."""
    return dict(BOND_EVENT_BASES)


def required_surfaces() -> list[str]:
    """Return the script surfaces the mapping must integrate with."""
    return list(REQUIRED_SURFACES)


def validate_feed_mapping(plan: Mapping) -> list[str]:
    """Check a feed/bond mapping plan against the mapped path."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Feed mapping plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected}."
            )
    surfaces = plan.get("surfaces") or {}
    for required in REQUIRED_SURFACES:
        if surfaces.get(required) is not True:
            errors.append(f"Mapping must integrate with {required}.")
    magnitudes = plan.get("magnitudes") or {}
    if magnitudes.get("substitutes_configured_magnitude") is not True:
        errors.append("Mapping must substitute the configured magnitude.")
    if magnitudes.get("keeps_item_hash_through_func_739") is not True:
        errors.append("Mapping must keep the item hash through func_739.")
    return errors

def validate_feed_config(config: Mapping) -> list[str]:
    """Check a per-item feed/bond configuration table.

    Every configured item must join the func_724 allowlist extension, and
    every magnitude must be a positive integer substituted inside the
    func_454 checks only.
    """
    errors: list[str] = []
    if not isinstance(config, Mapping):
        return ["Feed configuration must be a mapping."]
    items = config.get("items")
    if not isinstance(items, Mapping) or not items:
        return ["Feed configuration must map at least one item hash to a magnitude."]
    allowlist = config.get("allowlist_extension") or []
    for item_hash, magnitude in items.items():
        if not isinstance(item_hash, str) or not item_hash.strip():
            errors.append("Feed items must be named by item hash.")
            continue
        if not isinstance(magnitude, int) or isinstance(magnitude, bool) or magnitude <= 0:
            errors.append(
                f"Item {item_hash} needs a positive integer bond magnitude."
            )
        if item_hash not in allowlist:
            errors.append(
                f"Item {item_hash} must join the func_724 allowlist extension; "
                "a catalog tag alone cannot enroll it."
            )
    if config.get("substitution_point") != "func_454_magnitude_only":
        errors.append("Magnitudes substitute inside func_454 checks only.")
    return errors
