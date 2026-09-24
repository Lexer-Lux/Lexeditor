"""Measurable Viking Comb honor test: which gains the comb doubles (#202).

Issue 202 asks that carrying the Viking Comb double eligible small positive
social Honor gains, excluding missions, losses, and gains above 20 points.
The doubling hook itself is the same unproven honor-event interception path
as #161, so no hook is invented here. What this module pins down is the
measurability contract from the issue body: exactly which gains count as
eligible, and what a valid before/after measurement plan must cover, so a
future session can produce readable values instead of an unspecified
honor-bar judgement.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Gains above this value are outside the doubling rule.
MAX_DOUBLED_GAIN = 20

# A gain is eligible only when every one of these holds.
ELIGIBILITY_RULES = (
    "gain must be positive (losses never double)",
    "gain must be social (mission gains are excluded)",
    "gain must not come from a mission",
    f"gain must be at most {MAX_DOUBLED_GAIN} points",
)


def is_eligible_gain(amount: object, social: object, mission: object) -> bool:
    """Return True when a gain falls under the Viking Comb doubling rule."""
    return (
        isinstance(amount, (int, float))
        and not isinstance(amount, bool)
        and amount > 0
        and amount <= MAX_DOUBLED_GAIN
        and bool(social)
        and not bool(mission)
    )


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_measurement(plan: Mapping) -> list[str]:
    """Check a Viking Comb measurement plan; empty list means valid."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["plan must be a mapping"]
    interaction = plan.get("interaction")
    if not _non_empty_string(interaction):
        errors.append("interaction must name the known repeatable interaction")
    readings = plan.get("readings")
    if not isinstance(readings, Mapping):
        errors.append("readings must give before/after Honor values")
    else:
        for side in ("before", "after"):
            value = readings.get(side)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"readings.{side} must be a readable Honor value")
    cases = plan.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must list at least one measured gain")
        cases = []
    doubled = excluded = 0
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
        if not isinstance(case, Mapping):
            errors.append(f"{where} must be a mapping")
            continue
        amount, social, mission = case.get("amount"), case.get("social"), case.get("mission")
        if (
            not isinstance(amount, (int, float))
            or isinstance(amount, bool)
            or not isinstance(social, bool)
            or not isinstance(mission, bool)
        ):
            errors.append(f"{where} needs amount, social, and mission flags")
            continue
        eligible = is_eligible_gain(amount, social, mission)
        if eligible:
            doubled += 1
        else:
            excluded += 1
        expected = amount * 2 if eligible else amount
        if case.get("expected") != expected:
            errors.append(
                f"{where} must expect {expected} "
                f"({'doubled' if eligible else 'undoubled'})"
            )
    if cases and not doubled:
        errors.append("cases must include at least one doubled eligible gain")
    if cases and not excluded:
        errors.append("cases must include at least one excluded gain (mission, loss, or above 20)")
    unknowns = plan.get("open_unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("open_unknowns must state what is still unproven")
    elif not any(
        isinstance(item, str) and "intercept" in item.lower() for item in unknowns
    ):
        errors.append("open_unknowns must own the unproven honor-event interception hook")
    return errors


def is_valid(plan: Mapping) -> bool:
    """Return True when the measurement plan passes every structural check."""
    return not validate_measurement(plan)

def validate_session_result(result: Mapping) -> list[str]:
    """Check a Viking Comb session's recorded before/after readings."""
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return ["result must be a mapping"]
    interaction = result.get("interaction")
    if not _non_empty_string(interaction):
        errors.append("interaction must name the known repeatable interaction")
    cases = result.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must list at least one measured gain"]
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
        if not isinstance(case, Mapping):
            errors.append(f"{where} must be a mapping")
            continue
        amount, social, mission = case.get("amount"), case.get("social"), case.get("mission")
        if (
            not isinstance(amount, (int, float))
            or isinstance(amount, bool)
            or not isinstance(social, bool)
            or not isinstance(mission, bool)
        ):
            errors.append(f"{where} needs amount, social, and mission flags")
            continue
        before, after = case.get("before"), case.get("after")
        if (
            not isinstance(before, (int, float)) or isinstance(before, bool)
            or not isinstance(after, (int, float)) or isinstance(after, bool)
        ):
            errors.append(f"{where} must record readable before/after Honor values")
            continue
        expected = amount * 2 if is_eligible_gain(amount, social, mission) else amount
        if after - before != expected:
            errors.append(f"{where} observed {after - before}, expected {expected}")
    return errors
