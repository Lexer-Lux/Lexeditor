"""Saddle-lantern purchase path: which lanterns can actually be bought (#291).

Issue 291 needs the rider's belt lantern hidden while mounted and the
purchased horse lantern attached to the saddle horse. The recorded catalog
finding (queried via get_catalog('mine')) is:

- 5 lantern/lamp records exist.
- Only two are purchasable: the Halloween lantern at the fence (25450) and
  the saddle lantern at the horse shop (35000).
- The belt-relevant handhelds (WEAPON_MELEE_LANTERN,
  WEAPON_MELEE_DAVY_LANTERN) carry NO buy path and NO shop listings, so the
  belt lantern cannot be purchase-tested: its acquisition path must be
  loot/pickup, or a purchase route must be created first.

This module records that finding as checkable data and validates a
lantern-test plan: a purchase step must name a purchasable record, a belt
lantern step must use a non-purchase acquisition route, and the still-open
light-control fixes must be owned as unknowns instead of assumed done.
No gameplay claim: light-control fixes and the loot-path check still need
a real session; nothing here claims them.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Acquisitions that do not go through a shop.
NON_PURCHASE_ROUTES = ("loot", "pickup", "create_route")

LANTERN_RECORDS = (
    {
        "record": "WEAPON_MELEE_LANTERN",
        "role": "belt_handheld",
        "purchasable": False,
        "shop": None,
        "price": None,
    },
    {
        "record": "WEAPON_MELEE_DAVY_LANTERN",
        "role": "belt_handheld",
        "purchasable": False,
        "shop": None,
        "price": None,
    },
    {
        "record": "HALLOWEEN_LANTERN",
        "role": "handheld",
        "purchasable": True,
        "shop": "fence",
        "price": 25450,
    },
    {
        "record": "SADDLE_LANTERN",
        "role": "horse_lantern",
        "purchasable": True,
        "shop": "horse_shop",
        "price": 35000,
    },
)


def records() -> list[dict]:
    """Return a deep copy of the recorded lantern catalog finding."""
    return copy.deepcopy(list(LANTERN_RECORDS))


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_lantern_test(plan: Mapping) -> list[str]:
    """Check a saddle-lantern test plan; empty list means valid."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["plan must be a mapping"]
    by_record = {
        entry["record"]: entry for entry in LANTERN_RECORDS
        if isinstance(entry, Mapping)
    }
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list of acquisition/test steps")
        steps = []
    known_reference = False
    for index, step in enumerate(steps):
        where = f"steps[{index}]"
        if not isinstance(step, Mapping):
            errors.append(f"{where} must be a mapping")
            continue
        record = step.get("record")
        if not _non_empty_string(record):
            errors.append(f"{where} must name the lantern record under test")
            continue
        known = by_record.get(str(record).strip())
        if known is None:
            errors.append(f"{where} names unknown lantern record {record!r}")
            continue
        known_reference = True
        route = step.get("route")
        if known["purchasable"]:
            if route != "purchase":
                errors.append(
                    f"{where} tests purchasable {record} without a purchase route"
                )
            else:
                if step.get("shop") != known["shop"]:
                    errors.append(
                        f"{where} must buy {record} at {known['shop']}"
                    )
        else:
            if route == "purchase" or not _non_empty_string(route):
                errors.append(
                    f"{where} cannot purchase-test {record}: it has no buy path; "
                    f"use one of {list(NON_PURCHASE_ROUTES)}"
                )
            elif str(route).strip() not in NON_PURCHASE_ROUTES:
                errors.append(
                    f"{where} uses unknown acquisition route {route!r}"
                )
    if steps and not known_reference:
        errors.append("plan must exercise at least one recorded lantern record")
    unknowns = plan.get("open_unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("open_unknowns must state what is still unproven")
    elif not any(
        isinstance(item, str) and "light" in item.lower() for item in unknowns
    ):
        errors.append("open_unknowns must own the still-open light-control fixes")
    return errors


def is_valid(plan: Mapping) -> bool:
    """Return True when the lantern-test plan passes every structural check."""
    return not validate_lantern_test(plan)
