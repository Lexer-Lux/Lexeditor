"""Plant-density candidate contract (#229).

Issue 229 requires fewer plants without leaving visible plants that
cannot be picked. Disabling scenario points failed exactly that way and
stays rejected; animal-density multipliers cover animal spawns, not
plants. A real placement/spawn solution still needs engine research.

This module records that boundary as checkable data and validates a
density candidate: it must name a placement/spawn mechanism (not a
scenario-point-only disable) and prove remaining plants stay pickable.
No gameplay claim: the engine research and a real candidate are still
owed.
"""

from __future__ import annotations

from collections.abc import Mapping

# The failed implementation that must stay disabled.
REJECTED_MECHANISM = "scenario_point_disable_only"


def validate_density_candidate(candidate: Mapping) -> list[str]:
    """Check a plant-density candidate against the acceptance boundary."""
    errors: list[str] = []
    if not isinstance(candidate, Mapping):
        return ["Density candidate must be a mapping."]
    mechanism = str(candidate.get("mechanism", ""))
    if not mechanism:
        errors.append("Candidate must name its placement/spawn mechanism.")
    elif mechanism == REJECTED_MECHANISM:
        errors.append(
            "Scenario-point-only disable stays rejected: it leaves visible "
            "plants that cannot be picked."
        )
    if "animal" in mechanism and "plant" not in mechanism:
        errors.append(
            "Animal-density multipliers cover animal spawns, not plants."
        )
    if candidate.get("pickability_proof") in (None, ""):
        errors.append(
            "Candidate must prove remaining plants stay pickable."
        )
    if candidate.get("density_reduction") in (None, ""):
        errors.append(
            "Candidate must state the density reduction it targets."
        )
    return errors

def validate_field_survey(survey: Mapping) -> list[str]:
    """Check a density candidate's field survey and pickability proof."""
    errors: list[str] = []
    if not isinstance(survey, Mapping):
        return ["Field survey must be a mapping."]
    if survey.get("mechanism") in (None, ""):
        errors.append("Survey must name the surveyed placement/spawn mechanism.")
    elif survey.get("mechanism") == REJECTED_MECHANISM:
        errors.append(
            "Scenario-point-only disable stays rejected: it leaves visible "
            "plants that cannot be picked."
        )
    areas = survey.get("areas")
    if not isinstance(areas, list) or not areas:
        return errors + ["Survey must sample at least one area."]
    reduced = False
    for index, area in enumerate(areas):
        where = f"areas[{index}]"
        if not isinstance(area, Mapping):
            errors.append(f"{where} must be a mapping.")
            continue
        before, after = area.get("plants_before"), area.get("plants_after")
        if (
            not isinstance(before, int) or isinstance(before, bool)
            or not isinstance(after, int) or isinstance(after, bool)
        ):
            errors.append(f"{where} must record integer before/after plant counts.")
            continue
        if after < before:
            reduced = True
    if areas and not reduced:
        errors.append("Survey must show fewer plants in at least one area.")
    spot_checks = survey.get("pickability_spot_checks")
    if not isinstance(spot_checks, list) or not spot_checks:
        errors.append("Survey must spot-check remaining plants stay pickable.")
    else:
        for index, check in enumerate(spot_checks):
            if check is not True:
                errors.append(
                    f"pickability_spot_checks[{index}] must pass; visible "
                    "unpickable plants fail the candidate."
                )
    return errors
