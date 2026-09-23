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
