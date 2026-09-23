"""Calloway's Schofield prototype: unique-gun features as reusable gun parts.

Issue 107 asks that distinctive unique-gun features become unlockable parts
mixable with normal gunsmith customization, instead of permanently separate
unmodifiable weapons. Unique guns are standalone identities while ordinary
customization uses weapon-specific slots and component records that can carry
real accuracy, FOV, and damage modifiers, so the conversion is a
catalog/component plan rather than a stat toggle.

This module records the first proof candidate (Calloway's Schofield revolver
features onto its base Schofield platform) as checkable data and validates
that a plan is structurally complete: every part names its slot and carries a
real modifier, catalog and gunsmith entries exist, the pickup unlocks the
parts, the six in-game verifications are covered, and the engraved-mesh reuse
unknown is stated openly instead of assumed. In-game acceptance (visibility,
installation, persistence, dual wield, mission rewards, compendium credit)
still needs a real session; nothing here claims it.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Component records can carry these real modifiers; a part with none of them
# is a stat toggle, which the research comment explicitly rules out.
REAL_MODIFIER_KEYS = ("accuracy", "fov", "damage")

# Engraved-mesh reuse per part: "reused" (proven), "custom" (remodelled), or
# "unproven" (still the open model-compatibility question).
MESH_SOURCES = ("reused", "custom", "unproven")

# In-game verifications the research comment requires before design review.
REQUIRED_VERIFICATIONS = (
    "gunsmith_visibility",
    "installation",
    "save_persistence",
    "dual_wield",
    "mission_rewards",
    "compendium_credit",
)

CALLOWAY_SCHOFIELD_PROTOTYPE = {
    "source_unique": "WEAPON_REVOLVER_SCHOFIELD_CALLOWAY",
    "base_weapon": "WEAPON_REVOLVER_SCHOFIELD",
    "parts": [
        {
            "component": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_GRIP",
            "slot": "grip",
            "modifiers": {"damage": 0.0, "accuracy": 0.0},
            "engraved_mesh": "unproven",
            "note": "Distinctive grip character without a power bonus.",
        },
        {
            "component": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_BARREL",
            "slot": "barrel",
            "modifiers": {"accuracy": 0.05},
            "engraved_mesh": "unproven",
            "note": "Engraved barrel profile with a small steadied-aim gain.",
        },
        {
            "component": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_FRAME",
            "slot": "frame",
            "modifiers": {"fov": -1.0},
            "engraved_mesh": "unproven",
            "note": "Engraved frame finish with a slight aim-zoom shift.",
        },
    ],
    "catalog_entries": [
        {"entry": "CATALOG_CALLOWAY_GRIP", "unlocks": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_GRIP"},
        {"entry": "CATALOG_CALLOWAY_BARREL", "unlocks": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_BARREL"},
        {"entry": "CATALOG_CALLOWAY_FRAME", "unlocks": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_FRAME"},
    ],
    "gunsmith_entries": [
        {"entry": "GUNSMITH_CALLOWAY_SET", "base_weapon": "WEAPON_REVOLVER_SCHOFIELD"},
    ],
    "pickup_unlock": {
        "pickup": "PICKUP_CALLOWAY_SCHOFIELD",
        "unlocks": [
            "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_GRIP",
            "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_BARREL",
            "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_FRAME",
        ],
    },
    "verification": [
        {"id": "gunsmith_visibility", "description": "Parts appear at the gunsmith once unlocked."},
        {"id": "installation", "description": "Parts install onto the base Schofield and mix with normal options."},
        {"id": "save_persistence", "description": "Installed parts survive save and reload."},
        {"id": "dual_wield", "description": "Parts behave in dual-wield loadouts."},
        {"id": "mission_rewards", "description": "Mission reward flow still grants the pickup exactly once."},
        {"id": "compendium_credit", "description": "Compendium credits the source weapon after conversion."},
    ],
    "open_unknowns": [
        "Whether each engraved mesh can be reused as a component or needs custom model work.",
    ],
}


def prototype() -> dict:
    """Return a deep copy of the Calloway's Schofield prototype plan."""
    return copy.deepcopy(CALLOWAY_SCHOFIELD_PROTOTYPE)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_prototype(plan: Mapping) -> list[str]:
    """Check a unique-to-parts conversion plan; empty list means valid."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["plan must be a mapping"]
    source, base = plan.get("source_unique"), plan.get("base_weapon")
    if not _non_empty_string(source):
        errors.append("source_unique must be a non-empty weapon identity")
    if not _non_empty_string(base):
        errors.append("base_weapon must be a non-empty weapon identity")
    if (
        _non_empty_string(source)
        and _non_empty_string(base)
        and str(source).strip() == str(base).strip()
    ):
        errors.append("base_weapon must differ from the standalone unique identity")

    parts = plan.get("parts")
    components: set[str] = set()
    if not isinstance(parts, list) or not parts:
        errors.append("parts must be a non-empty list of component conversions")
        parts = []
    for index, part in enumerate(parts):
        where = f"parts[{index}]"
        if not isinstance(part, Mapping):
            errors.append(f"{where} must be a mapping")
            continue
        component, slot = part.get("component"), part.get("slot")
        if not _non_empty_string(component):
            errors.append(f"{where} needs a component identifier")
        elif component in components:
            errors.append(f"{where} duplicates component {component}")
        else:
            components.add(component)
        if not _non_empty_string(slot):
            errors.append(f"{where} must name the base-weapon slot it fits")
        modifiers = part.get("modifiers")
        if not isinstance(modifiers, Mapping) or not any(
            key in modifiers for key in REAL_MODIFIER_KEYS
        ):
            errors.append(
                f"{where} must carry a real accuracy, fov, or damage modifier "
                "(a stat toggle is not a component conversion)"
            )
        if part.get("engraved_mesh") not in MESH_SOURCES:
            errors.append(f"{where} must state engraved_mesh as one of {list(MESH_SOURCES)}")

    for section in ("catalog_entries", "gunsmith_entries"):
        entries = plan.get(section)
        if not isinstance(entries, list) or not entries:
            errors.append(f"{section} must list at least one entry")
            continue
        for index, entry in enumerate(entries):
            where = f"{section}[{index}]"
            if not isinstance(entry, Mapping) or not _non_empty_string(entry.get("entry")):
                errors.append(f"{where} needs an entry identifier")
                continue
            target = entry.get("unlocks", entry.get("base_weapon"))
            if section == "catalog_entries" and target not in components:
                errors.append(f"{where} must unlock one of the planned components")

    pickup = plan.get("pickup_unlock")
    if not isinstance(pickup, Mapping) or not _non_empty_string(pickup.get("pickup")):
        errors.append("pickup_unlock must name the pickup that grants the parts")
    else:
        unlocks = pickup.get("unlocks")
        if not isinstance(unlocks, list) or not unlocks:
            errors.append("pickup_unlock must unlock at least one planned component")
        else:
            for component in unlocks:
                if component not in components:
                    errors.append(f"pickup_unlock grants {component}, which is not a planned part")

    verification = plan.get("verification")
    if not isinstance(verification, list):
        errors.append("verification must list the required in-game checks")
    else:
        covered = {
            item.get("id") for item in verification if isinstance(item, Mapping)
        }
        for required in REQUIRED_VERIFICATIONS:
            if required not in covered:
                errors.append(f"verification must cover {required}")

    unknowns = plan.get("open_unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("open_unknowns must state what is still unproven")
    elif any(
        isinstance(part, Mapping) and part.get("engraved_mesh") == "unproven"
        for part in parts
    ) and not any(
        isinstance(item, str) and "mesh" in item.lower() for item in unknowns
    ):
        errors.append("open_unknowns must own the unproven engraved-mesh reuse question")

    return errors


def is_valid(plan: Mapping) -> bool:
    """Return True when the plan passes every structural check."""
    return not validate_prototype(plan)
