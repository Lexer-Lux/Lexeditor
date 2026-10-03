"""Numeric conversion for editor writes: validate without rounding or truncation."""
from __future__ import annotations

import math
import re


def integer_value(value, label: str, error_type=ValueError) -> int:
    if isinstance(value, bool):
        raise error_type(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        try:
            return int(value)
        except ValueError:
            pass
    raise error_type(f"{label} must be an integer")


def finite_number(value, label: str, error_type=ValueError) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise error_type(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise error_type(f"{label} must be a finite number") from error
    if not math.isfinite(number):
        raise error_type(f"{label} must be a finite number")
    return number
