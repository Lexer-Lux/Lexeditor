"""Modular Story Mode bugfix collection manifest (#159).

Issue 159 prepares independently verified, permission-compatible fixes
as a modular pack: the candidates are separate problems, not one patch.
The audit names six unrelated mechanisms (Nexus 4909 v1.00 clothing
physics, 1425 corn-sack carry physics, 1197 Message timer regression,
704 run/walk toggle, 2953 Wickiup minimap YTD, 9006 completed
Dreamcatcher cleanup) with Wickiup map artwork and Dreamcatcher cleanup
as the best first targets. Clothing and carry physics need asset
regression comparisons, most cited pages restrict reuse, and the
run/walk toggle is a preference rather than a confirmed bug.

This module records that manifest schema as checkable data and
validates a collection plan: every fix ships independently with its own
verification and permission record, and excluded candidates stay out.
No gameplay claim: delivering the separate verified fixes still needs
the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Audit candidates that need asset regression comparisons first.
COMPARISON_CANDIDATES = (
    "nexus_4909_clothing_physics",
    "nexus_1425_carry_physics",
)

# First targets proposed by the audit.
FIRST_TARGETS = (
    "wickiup_map_artwork",
    "dreamcatcher_cleanup",
)

# Entries that must not ship as bugfixes.
EXCLUDED_ENTRIES = (
    "run_walk_toggle_preference",
    "monolithic_combined_patch",
)


def first_targets() -> list[str]:
    """Return the audit's proposed first targets."""
    return list(FIRST_TARGETS)


def validate_bugfix_collection(plan: Mapping) -> list[str]:
    """Check a bugfix-collection plan against the manifest schema."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Bugfix collection plan must be a mapping."]
    for excluded in EXCLUDED_ENTRIES:
        entries = plan.get("entries") or {}
        if entries.get(excluded) is True:
            errors.append(f"Collection must not ship {excluded}.")
    for name, entry in (plan.get("entries") or {}).items():
        if not isinstance(entry, Mapping):
            errors.append(f"Entry {name} must be a mapping.")
            continue
        for required in ("problem", "verification", "permission"):
            if not entry.get(required):
                errors.append(f"Entry {name} must record {required}.")
        if name in COMPARISON_CANDIDATES and not entry.get(
            "asset_regression_comparison"
        ):
            errors.append(
                f"Entry {name} needs an asset regression comparison first."
            )
    if not plan.get("ships_independently"):
        errors.append("Fixes must ship as independently verified entries.")
    return errors


# Game-side fix manifests for the two first targets. Each manifest states
# the exact problem, how it is verified against current files, and the
# permission basis, so the game-side delivery has a checkable record per
# fix instead of a shared note.
FIRST_TARGET_MANIFESTS = (
    {
        "entry": "wickiup_map_artwork",
        "problem": "Misnamed Wickiup minimap YTD (Nexus 2953).",
        "verification": "Corrected YTD name checked against current files.",
        "permission": "Credited reuse explicitly allowed.",
    },
    {
        "entry": "dreamcatcher_cleanup",
        "problem": "Completed Dreamcatchers entry lingers (Nexus 9006).",
        "verification": "Entry removed through a standalone ASI check.",
        "permission": "Recreated from vanilla/current assets or permitted.",
    },
)


def first_target_manifests() -> list[dict]:
    """Return independent copies of the first-target fix manifests."""
    return [dict(entry) for entry in FIRST_TARGET_MANIFESTS]


def validate_first_target_manifests(manifests) -> list[str]:
    """Check the game-side manifests for the two first targets."""
    errors: list[str] = []
    if not isinstance(manifests, Mapping):
        return ["First-target manifests must be a mapping."]
    for target in FIRST_TARGETS:
        entry = manifests.get(target)
        if not isinstance(entry, Mapping):
            errors.append(f"First target {target} needs a fix manifest.")
            continue
        for required in ("problem", "verification", "permission"):
            if not entry.get(required):
                errors.append(
                    f"Manifest {target} must record {required}."
                )
    for name in manifests:
        if name not in FIRST_TARGETS:
            errors.append(
                f"Manifest {name} is not a first target; "
                "later fixes ship under the collection schema."
            )
    return errors

# Fields each delivered fix must record: what basis it was built from, how
# it was verified against current files, and that it ships independently.
DELIVERY_RECORD_FIELDS = ("built_from", "verification", "ships_independently")


def validate_delivery_record(record: Mapping) -> list[str]:
    """Check one delivered fix against the modular delivery contract."""
    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["Delivery record must be a mapping."]
    entry = str(record.get("entry", ""))
    if not entry:
        errors.append("Delivery record must name its collection entry.")
    elif entry in EXCLUDED_ENTRIES:
        errors.append(f"Delivery record must not ship {entry}.")
    for field in DELIVERY_RECORD_FIELDS:
        if not record.get(field):
            errors.append(f"Delivery record must state {field}.")
    if entry in COMPARISON_CANDIDATES and not record.get("asset_regression_comparison"):
        errors.append(
            f"Entry {entry} needs an asset regression comparison first."
        )
    return errors
