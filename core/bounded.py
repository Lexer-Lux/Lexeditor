"""One place for "a number within its own bounds, or say which and why".

Four plugin modules validated a value against its bounds and each wrote the
same lines: refuse a bool, cast, refuse anything outside the range, return it.
Only the bounds, the wording of the label and the exception type are the
caller's, so those are the parameters and the rest lives here once.

    tick = whole_number(edit.get("tickSpeed"), "Tick speed", 0, 0xFF, CtbBaseError)
"""

from __future__ import annotations


def whole_number(value, label: str, low: int, high: int,
                 error: type[Exception] = ValueError) -> int:
    """`value` as a whole number from low through high, or `error`."""
    if isinstance(value, bool):
        raise error(f"{label} must be a whole number")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as cause:
        raise error(f"{label} must be a whole number") from cause
    if not low <= parsed <= high:
        raise error(f"{label} must be between {low} and {high}")
    return parsed


def decimal(value, label: str, low: float, high: float,
            error: type[Exception] = ValueError) -> float:
    """`value` as a number from low through high, or `error`."""
    if isinstance(value, bool):
        raise error(f"{label} must be a number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as cause:
        raise error(f"{label} must be a number") from cause
    if not low <= parsed <= high:
        raise error(f"{label} must be between {low:g} and {high:g}")
    return parsed
