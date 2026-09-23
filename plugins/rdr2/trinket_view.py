"""Separate trinket inventory view proposal contract (#136).

Issue 136 requires a separate owned-trinket view without pretending a
new native satchel category is already supported. Catalog metadata
cannot add a tab: satchel_ui_event_handler builds fixed
Satchel/category/menu/list containers with hardcoded trinket/talisman
handling. Two routes remain: prove the authored movie accepts an
injected category through one isolated datastore-injection probe, or
build a native-looking mod-owned page with only owned trinkets.

This module records that presentation contract as checkable data and
validates a proposal: a mod-owned page must be read-only, list only
owned trinkets, and handle selection plus Back, while any native-tab
claim needs the completed injection probe. No gameplay claim: the probe
and the Lexer presentation choice still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Requirements for the mod-owned separate page route.
PAGE_REQUIREMENTS = (
    "owned_only_membership",
    "read_only_no_equip_discard_activate",
    "selected_name_and_effect_details",
    "keyboard_selection",
    "back_request",
)

# Requirements for the native-tab route.
NATIVE_TAB_REQUIREMENTS = (
    "isolated_datastore_injection_probe",
    "category_filter_selection_proof",
    "focus_and_back_handling",
    "sizing_proof",
)

# Claims the issue discussion already rejected.
REJECTED_CLAIMS = (
    "catalog_metadata_adds_tab",
    "new_native_category_supported",
)


def page_requirements() -> list[str]:
    """Return the mod-owned page requirements."""
    return list(PAGE_REQUIREMENTS)


def native_tab_requirements() -> list[str]:
    """Return the native-tab route requirements."""
    return list(NATIVE_TAB_REQUIREMENTS)


def validate_trinket_proposal(plan: Mapping) -> list[str]:
    """Check a trinket-view proposal against the contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Trinket proposal must be a mapping."]
    route = str(plan.get("route", ""))
    claim = str(plan.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim or rejected in route:
            errors.append(
                f"Proposal reuses the rejected claim {rejected}."
            )
    if route == "mod_owned_page":
        page = plan.get("page") or {}
        for required in PAGE_REQUIREMENTS:
            if page.get(required) is not True:
                errors.append(f"Mod-owned page must provide {required}.")
    elif route == "native_tab":
        probe = plan.get("probe") or {}
        for required in NATIVE_TAB_REQUIREMENTS:
            if probe.get(required) is not True:
                errors.append(f"Native-tab route must prove {required}.")
    else:
        errors.append("Proposal must select mod_owned_page or native_tab.")
    return errors
