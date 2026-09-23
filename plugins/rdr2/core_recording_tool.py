"""Synchronized core-trace recording tool specification (#177).

Issue 177 needs a synchronized core-value trace plus video to separate
artwork stepping from update timing: core state is integer-only 0-100,
so the recorder must sample that integer every frame beside a video of
a slow vanilla drain/restore. The measurement contract (fixed cadence,
monotonic timebase, paired video, exact restoration/drain legs) lives
in core_trace.py; this module specifies the recording tool itself plus
a validator for the trace records it must produce. A gameplay tween or
overlay must never be presented as the fix.

This module records the recorder specification as checkable data,
validates a recorder plan, and validates recorded sample sequences:
positive fixed cadence, monotonic timestamps within tolerance, integer
0-100 core values, and a bound video reference. No gameplay claim: the
tool build, the capture session, and any smoothing decision are owed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# Core state is integer-only 0-100; the recorder samples that integer.
CORE_MIN = 0
CORE_MAX = 100

# Fields a recorder plan must name.
REQUIRED_PLAN_FIELDS = (
    "cadence_hz",
    "timebase",
    "sample_fields",
    "output_format",
    "video_pairing",
    "sequence_binding",
)

# Fields every recorded sample must carry.
REQUIRED_SAMPLE_FIELDS = (
    "timestamp",
    "core_value",
)

# Approaches the issue discussion already rejected.
REJECTED_APPROACHES = (
    "gameplay_tween",
    "overlay",
    "openiv_only",
)


def validate_recorder_plan(plan: Mapping) -> list[str]:
    """Check a core-recorder plan against the tool specification."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Recorder plan must be a mapping."]
    for field in REQUIRED_PLAN_FIELDS:
        if not plan.get(field):
            errors.append(f"Recorder plan must name {field}.")
    cadence = plan.get("cadence_hz")
    if cadence is not None and (
        not isinstance(cadence, (int, float)) or cadence <= 0
    ):
        errors.append("Recorder cadence must be a positive rate in Hz.")
    if plan.get("timebase") != "monotonic":
        errors.append("Recorder samples must use a monotonic timebase.")
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} cannot answer the timing question."
            )
    return errors


def validate_trace_records(
    samples: Sequence[Mapping], cadence_hz: float
) -> list[str]:
    """Check recorded samples: cadence, monotonic time, integer 0-100."""
    errors: list[str] = []
    if not isinstance(cadence_hz, (int, float)) or cadence_hz <= 0:
        return ["Trace cadence must be a positive rate in Hz."]
    rows = list(samples or [])
    if not rows:
        return ["Trace must contain at least one sample."]
    expected_gap = 1.0 / float(cadence_hz)
    previous_time: float | None = None
    for index, sample in enumerate(rows):
        where = f"sample[{index}]"
        if not isinstance(sample, Mapping):
            errors.append(f"{where} must be a mapping.")
            continue
        for field in REQUIRED_SAMPLE_FIELDS:
            if field not in sample:
                errors.append(f"{where} must carry {field}.")
        timestamp = sample.get("timestamp")
        value = sample.get("core_value")
        if not isinstance(timestamp, (int, float)):
            errors.append(f"{where} timestamp must be numeric.")
        elif previous_time is not None:
            gap = timestamp - previous_time
            if gap <= 0:
                errors.append(f"{where} timestamp is not monotonic.")
            elif abs(gap - expected_gap) > 0.5 * expected_gap:
                errors.append(
                    f"{where} gap {gap:.4f}s breaks the fixed cadence."
                )
        if isinstance(timestamp, (int, float)):
            previous_time = timestamp
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not (CORE_MIN <= value <= CORE_MAX)
        ):
            errors.append(
                f"{where} core_value must be an integer "
                f"{CORE_MIN}-{CORE_MAX}."
            )
    return errors
