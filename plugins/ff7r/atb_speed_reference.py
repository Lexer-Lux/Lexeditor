"""Empirical FF7R passive-ATB Speed reference constraints for issue #425.

A detailed 2020 Remake combat measurement records one displayed ATB bar fill
at several Dexterity/Speed values with +/-0.005 s timing precision, plus matching
Haste measurements. The points are valuable for validating a future installed
native formula, but a regression fit through them is not the game's formula.

Source measurements:
https://www.gamersky.com/handbook/202005/1291539.shtml

This module contains no runtime mutation and deliberately marks every derived fit
as descriptive-only.
"""

from __future__ import annotations

import math
from typing import Any, Iterable


INTERNAL_UNITS_PER_DISPLAYED_BAR = 1000.0
MEASUREMENT_TOLERANCE_SECONDS = 0.005
DOCUMENTED_HASTE_MULTIPLIER = 1.4

PASSIVE_ONE_BAR_SECONDS = (
    (45, 13.850),
    (50, 13.745),
    (55, 13.660),
    (65, 13.525),
    (80, 13.365),
)

HASTE_ONE_BAR_SECONDS = (
    (50, 9.825),
    (55, 9.765),
    (65, 9.665),
    (80, 9.545),
)


def _linear_fit(points: Iterable[tuple[float, float]]) -> tuple[float, float]:
    rows = tuple((float(x), float(y)) for x, y in points)
    if len(rows) < 2:
        raise ValueError("at least two points are required for a descriptive linear fit")
    mean_x = sum(x for x, _ in rows) / len(rows)
    mean_y = sum(y for _, y in rows) / len(rows)
    denominator = sum((x - mean_x) ** 2 for x, _ in rows)
    if denominator == 0:
        raise ValueError("Speed samples must contain at least two distinct values")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in rows) / denominator
    return mean_y - slope * mean_x, slope


def analyze_speed_measurement_reference() -> dict[str, Any]:
    """Return descriptive constraints for validating a future native formula."""
    passive = [
        {
            "speed": speed,
            "oneBarSeconds": seconds,
            "internalUnitsPerSecond": INTERNAL_UNITS_PER_DISPLAYED_BAR / seconds,
        }
        for speed, seconds in PASSIVE_ONE_BAR_SECONDS
    ]
    rate_points = [
        (row["speed"], row["internalUnitsPerSecond"])
        for row in passive
    ]
    intercept, slope = _linear_fit(rate_points)
    fit_rows = []
    for row in passive:
        predicted_rate = intercept + slope * row["speed"]
        predicted_seconds = INTERNAL_UNITS_PER_DISPLAYED_BAR / predicted_rate
        fit_rows.append({
            **row,
            "descriptivePredictedSeconds": predicted_seconds,
            "descriptiveResidualSeconds": predicted_seconds - row["oneBarSeconds"],
        })

    passive_by_speed = {speed: seconds for speed, seconds in PASSIVE_ONE_BAR_SECONDS}
    haste_rows = []
    for speed, haste_seconds in HASTE_ONE_BAR_SECONDS:
        normal_seconds = passive_by_speed.get(speed)
        if normal_seconds is None:
            continue
        observed_multiplier = normal_seconds / haste_seconds
        haste_rows.append({
            "speed": speed,
            "normalOneBarSeconds": normal_seconds,
            "hasteOneBarSeconds": haste_seconds,
            "observedRateMultiplier": observed_multiplier,
            "errorFromDocumented1_4x": observed_multiplier - DOCUMENTED_HASTE_MULTIPLIER,
        })
    mean_haste = (
        sum(row["observedRateMultiplier"] for row in haste_rows) / len(haste_rows)
        if haste_rows else None
    )

    return {
        "exactSpeedFormulaValidated": False,
        "descriptiveFitOnly": True,
        "internalUnitsPerDisplayedBar": INTERNAL_UNITS_PER_DISPLAYED_BAR,
        "measurementToleranceSeconds": MEASUREMENT_TOLERANCE_SECONDS,
        "passiveSamples": passive,
        "descriptiveLinearRateFit": {
            "interceptInternalUnitsPerSecond": intercept,
            "slopeInternalUnitsPerSecondPerSpeed": slope,
            "maxAbsoluteTimeResidualSeconds": max(
                abs(row["descriptiveResidualSeconds"]) for row in fit_rows
            ),
            "samples": fit_rows,
        },
        "hasteReference": {
            "documentedMultiplier": DOCUMENTED_HASTE_MULTIPLIER,
            "meanObservedMultiplier": mean_haste,
            "samples": haste_rows,
        },
        "notes": [
            "The measured Speed points constrain any future reverse-engineered passive ATB formula but do not identify its exact arithmetic, tick cadence, rounding, or intermediate units.",
            "The linear rate fit is descriptive only. It must never be used as the gameplay implementation merely because it approximates the measured samples.",
            "The Haste samples independently reproduce approximately 1.4x passive ATB rate across several Speed values, making them useful composition checks for a future native formula.",
            "No ResidentParameter row, executable function, or runtime setting is selected or modified by this reference module.",
        ],
    }
