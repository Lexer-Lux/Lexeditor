"""Camera profiles and vehicle-framing contract (#108).

Issue 108 keeps eight gameplay-camera profiles (standing, crouched, prone,
horseback, vehicle, aim, crouched aim, armed, crouched armed) with
developer-mode-gated authoring and a separate saved-preset apply path.
The proven gameplay-camera native exposes horizontal offset and distance
only: continuous vertical positioning does not exist, and vehicle framing
stays on the binary LOW/NORMAL handoff owned by the two-mode handoff in
#220. Shoulder placement stays #267.

This module records that framing contract as checkable data and validates
a framing plan: every profile names its fields, vehicle framing uses the
binary states only, no plan claims a continuous Y control or a vehicle
height mapping, and authoring stays dev-mode gated. No gameplay claim:
vehicle-height research and the open shoulder/transition defect sessions
still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Profiles the module must keep. Developer mode gates editing, not the
# application of saved profiles.
PROFILES = (
    "standing",
    "crouched",
    "prone",
    "horseback",
    "vehicle",
    "aim",
    "crouched_aim",
    "armed",
    "crouched_armed",
)

# The only real vertical/framing control the proven native path exposes.
VEHICLE_FRAMING_STATES = ("LOW", "NORMAL")

# Claims the issue discussion already rejected.
REJECTED_CLAIMS = (
    "continuous_y_positioning",
    "vehicle_height_mapping",
    "fake_y_control",
)


def profiles() -> list[str]:
    """Return the camera profiles the contract keeps."""
    return list(PROFILES)


def vehicle_framing_states() -> list[str]:
    """Return the proven binary vehicle-framing states."""
    return list(VEHICLE_FRAMING_STATES)


def validate_framing_plan(plan: Mapping) -> list[str]:
    """Check a camera-framing plan against the proven contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Framing plan must be a mapping."]
    claim = str(plan.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim:
            errors.append(
                f"Plan reuses the rejected claim {rejected}: the proven "
                "native exposes horizontal offset and distance only."
            )
    covered = plan.get("profiles") or {}
    for required in PROFILES:
        if not covered.get(required):
            errors.append(f"Framing plan must keep the {required} profile.")
    vehicle = covered.get("vehicle") or {}
    if isinstance(covered, Mapping) and isinstance(vehicle, Mapping):
        states = vehicle.get("framing_states") or []
        for state in states:
            if state not in VEHICLE_FRAMING_STATES:
                errors.append(
                    f"Vehicle framing state {state!r} is unproven; "
                    "only LOW/NORMAL are established."
                )
    if plan.get("authoring_gated_by_developer_mode") is not True:
        errors.append(
            "Camera authoring must stay gated by developer mode."
        )
    if plan.get("vehicle_handoff_owner", "") != "#220":
        errors.append(
            "The two-mode vehicle handoff stays owned by #220."
        )
    return errors

# Fields a saved-preset apply record must name. Applying a saved preset is
# the ungated path: developer mode gates authoring, never application.
APPLY_FIELDS = ("profile", "values")


def validate_preset_apply(request: Mapping) -> list[str]:
    """Check a saved-preset apply request against the contract."""
    errors: list[str] = []
    if not isinstance(request, Mapping):
        return ["Preset apply request must be a mapping."]
    if request.get("profile") not in PROFILES:
        errors.append("Preset apply must name one of the kept profiles.")
    if not isinstance(request.get("values"), Mapping) or not request["values"]:
        errors.append("Preset apply must carry the saved profile values.")
    if request.get("requires_developer_mode") is True:
        errors.append(
            "Applying a saved preset must not require developer mode; "
            "the gate covers authoring only."
        )
    claim = str(request.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim:
            errors.append(
                f"Preset apply reuses the rejected claim {rejected}."
            )
    return errors
