"""Replacement-icon preview gate (#111).

Issue 111 is an artwork-quality task: casing, ammunition, and bottle icons
appear but look poor, and replacement previews must come before any
approval ask. Unapproved YTD must not ship. The in-game pickup and
acquisition-card check with the art toolchain still needs a real session.

This module records the preview gate as checkable data and validates a
replacement plan: every replaced family names its preview, previews come
before approval, approval comes before shipping, and families still on a
temporary vanilla fallback (shotgun hulls) or with no checked-in source
(hulls generally) cannot be presented as finished. No art claim: quality
and Lexer approval still need the art toolchain and a game check.
"""

from __future__ import annotations

from collections.abc import Mapping

# Replacement families under discussion, with their current artwork state:
# "previewed" (custom drawing with a review preview), "vanilla_fallback"
# (temporarily showing a vanilla icon), or "no_source" (no checked-in
# custom artwork yet).
REPLACEMENT_FAMILIES = (
    {"family": "pistol_casings", "state": "previewed"},
    {"family": "revolver_casings", "state": "previewed"},
    {"family": "repeater_casings", "state": "previewed"},
    {"family": "rifle_casings", "state": "previewed"},
    {"family": "shotgun_hulls", "state": "vanilla_fallback"},
    {"family": "varmint_casings", "state": "previewed"},
    {"family": "cartridge_225_casings", "state": "previewed"},
    {"family": "ammo_225_ap", "state": "previewed"},
    {"family": "empty_bottle", "state": "previewed"},
)

FINISHED_STATES = ("previewed",)
UNFINISHED_STATES = ("vanilla_fallback", "no_source")


def replacement_families() -> list[dict]:
    """Return the replacement families with their artwork states."""
    return [dict(entry) for entry in REPLACEMENT_FAMILIES]


def validate_replacement_plan(plan: Mapping) -> list[str]:
    """Check a replacement-icon plan against the preview gate."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Replacement plan must be a mapping."]
    known = {entry["family"]: entry["state"] for entry in REPLACEMENT_FAMILIES}
    families = plan.get("families") or {}
    if not isinstance(families, Mapping) or not families:
        return ["Replacement plan must name at least one family."]
    for family, record in families.items():
        if family not in known:
            errors.append(f"Family {family!r} is not a tracked replacement.")
            continue
        if not isinstance(record, Mapping):
            errors.append(f"Family {family} must be a mapping.")
            continue
        if record.get("preview_shown") is not True:
            errors.append(
                f"Family {family} needs its replacement preview before "
                "any approval ask."
            )
        if record.get("ship", False) is True:
            if known[family] in UNFINISHED_STATES:
                errors.append(
                    f"Family {family} is still {known[family]} and must "
                    "not ship."
                )
            if record.get("approved") is not True:
                errors.append(
                    f"Family {family} must have explicit approval before "
                    "its YTD ships."
                )
    return errors
