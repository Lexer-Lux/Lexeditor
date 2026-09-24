"""Independent-hunting-tracks experiment protocol (#133).

Issue 133 asks whether hunting can start from independent tracks under
low incidental animal density. Static research does not support
free-standing ambient spoor: Story scripts manipulate tracking
prompts/tutorials while ordinary trails stay tied to a live or recently
streamed ped, mission TRACKS strings are UI/mission state, and
effects/snowtracks.xml tunes footprint appearance only. Near-zero
density therefore cannot rely on vanilla tracks.

This module records the controlled probe the issue requires as
checkable data: measure trail lifetime after a tagged animal streams
out versus explicit deletion, then choose between the two viable
designs (a hidden/distant target ped whose trail is preserved until
discovery, or custom signs leading to a later spawn). No gameplay
claim: the probe and the design choice still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Measurements the controlled probe must record before any design choice.
REQUIRED_MEASUREMENTS = (
    "trail_lifetime_after_stream_out",
    "trail_lifetime_after_explicit_deletion",
    "tagged_animal_identity",
    "streaming_conditions",
)

# Designs the evidence leaves viable once the probe is measured.
VIABLE_DESIGNS = (
    "hidden_distant_target_ped",
    "custom_signs_with_later_spawn",
)

# Choices the issue discussion already rejected without probe evidence.
REJECTED_CHOICES = (
    "native_trails_without_evidence",
    "custom_signs_without_evidence",
    "vanilla_tracks_under_near_zero_density",
)


def required_measurements() -> list[str]:
    """Return the measurements the controlled probe must record."""
    return list(REQUIRED_MEASUREMENTS)


def viable_designs() -> list[str]:
    """Return the designs the evidence leaves viable."""
    return list(VIABLE_DESIGNS)


def validate_track_experiment(plan: Mapping) -> list[str]:
    """Check a hunting-tracks experiment plan against the protocol."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Track experiment plan must be a mapping."]
    choice = str(plan.get("design_choice", ""))
    for rejected in REJECTED_CHOICES:
        if rejected in choice:
            errors.append(
                f"Choice {choice!r} reuses the rejected {rejected} position."
            )
    measurements = plan.get("measurements") or {}
    for required in REQUIRED_MEASUREMENTS:
        if measurements.get(required) is not True:
            errors.append(f"Probe must record {required}.")
    if choice and choice not in VIABLE_DESIGNS and not any(
        rejected in choice for rejected in REJECTED_CHOICES
    ):
        errors.append(
            f"Design choice {choice!r} is not one of the viable designs."
        )
    if choice in VIABLE_DESIGNS and not measurements.get(
        "trail_lifetime_after_stream_out"
    ):
        errors.append(
            "A design choice requires the completed stream-out probe first."
        )
    return errors

# Fields a completed probe run must record per measurement: the observed
# value plus the conditions under which it was observed.
PROBE_RECORD_FIELDS = ("value", "conditions")


def validate_probe_result(result: Mapping) -> list[str]:
    """Check a completed trail-lifetime probe run and its design read."""
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return ["Probe result must be a mapping."]
    measurements = result.get("measurements")
    if not isinstance(measurements, Mapping) or not measurements:
        return ["Probe result must record the controlled measurements."]
    for required in REQUIRED_MEASUREMENTS:
        record = measurements.get(required)
        if not isinstance(record, Mapping):
            errors.append(f"Probe result must record {required}.")
            continue
        for field in PROBE_RECORD_FIELDS:
            if record.get(field) in (None, ""):
                errors.append(f"Measurement {required} must state {field}.")
    decision = str(result.get("design_decision", ""))
    if decision:
        if decision in REJECTED_CHOICES:
            errors.append(
                f"Decision {decision!r} reuses a rejected position."
            )
        elif decision not in VIABLE_DESIGNS:
            errors.append(
                f"Decision {decision!r} is not one of the viable designs."
            )
    return errors
