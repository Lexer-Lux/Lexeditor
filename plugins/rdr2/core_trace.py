"""Synchronized core-animation measurement contract (#177).

Issue 177 needs a synchronized core-value trace plus video to separate
artwork stepping from update timing. Static research is done (16 staged
artwork states); no smoothing change exists to test, and a gameplay tween
or overlay must never be presented as the fix.

This module records the measurement contract as checkable data and
validates a measurement plan: fixed-cadence integer core samples with a
monotonic timebase, a paired video reference, and the exact named
restoration/drain sequence. No gameplay claim: the recording tool, the
capture session, and any smoothing decision are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping

# Core state is integer-only 0-100; the trace must sample that integer.
CORE_MIN = 0
CORE_MAX = 100

# A plan must name all of these to be measurable.
REQUIRED_FIELDS = (
    "cadence_hz",
    "timebase",
    "video_reference",
    "sequence",
    "open_unknowns",
)

# Sequence kinds the issue discussion already settled as the remaining
# question: a restoration leg and a drain leg with exact steps.
REQUIRED_SEQUENCE_LEGS = ("restoration", "drain")


def validate_measurement_plan(plan: Mapping) -> list[str]:
    """Check a core-trace measurement plan against the contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Measurement plan must be a mapping."]
    for field in REQUIRED_FIELDS:
        if not plan.get(field):
            errors.append(f"Measurement plan must name {field}.")
    cadence = plan.get("cadence_hz")
    if cadence is not None and (not isinstance(cadence, (int, float)) or cadence <= 0):
        errors.append("Trace cadence must be a positive samples-per-second rate.")
    if str(plan.get("timebase", "")) != "monotonic":
        errors.append("Trace samples must use a monotonic timebase.")
    sequence = plan.get("sequence")
    if isinstance(sequence, Mapping):
        for leg in REQUIRED_SEQUENCE_LEGS:
            if not sequence.get(leg):
                errors.append(
                    f"Sequence must include an exact {leg} leg."
                )
    approach = str(plan.get("approach", ""))
    for rejected in ("tween", "overlay", "openiv_only"):
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} cannot answer the timing question: "
                "no gameplay tween/overlay, and no repeated OpenIV inspection."
            )
    return errors
