"""Built-in weight/mounted core-drain modifier boundary (#226).

Issue 226 requires removing the built-in weight and mounted core-drain
terms, not changing unrelated rates. The evidenced forecast math
(short_update func_2976: +0.15 perfect weight, -0.25 either extreme;
func_3740: +0.25 when mounted) is discarded by func_1632 and only feeds
screen-label writes, so patching it changes the display, not the drain.
Global fields 49/50/51 feed the formulas but are shared with
trinket/outfit benefits and are unsafe to zero.

This module records that boundary as checkable data and validates a
removal proposal: it must name the engine decrement routine, reject
forecast-only and shared-field edits, and own the unproven ownership
and cadence as open unknowns. No gameplay claim: identifying the engine
routine and proving ownership still need a matching game binary.
"""

from __future__ import annotations

from collections.abc import Mapping

# Evidenced UI-forecast terms. Display only: func_1632 discards them.
FORECAST_TERMS = (
    {"term": "perfect_weight", "value": 0.15, "source": "short_update func_2976"},
    {"term": "extreme_weight", "value": -0.25, "source": "short_update func_2976"},
    {"term": "mounted", "value": 0.25, "source": "short_update func_3740"},
)

# Routines whose outputs never reach the real drain.
FORECAST_ONLY_ROUTINES = (
    "func_2976",
    "func_3740",
    "func_2880",
    "func_2881",
    "func_2882",
    "pause_menu func_70",
    "pause_menu func_71",
)

# Persisted fields shared with trinket/outfit benefits: not safe targets.
SHARED_FIELDS = ("Global_49", "Global_50", "Global_51")


def forecast_terms() -> list[dict]:
    """Return an independent copy of the evidenced forecast terms."""
    return [dict(term) for term in FORECAST_TERMS]


def validate_removal_proposal(proposal: Mapping) -> list[str]:
    """Check a modifier-removal proposal against the evidenced boundary."""
    errors: list[str] = []
    if not isinstance(proposal, Mapping):
        return ["Removal proposal must be a mapping."]
    if not proposal.get("engine_routine"):
        errors.append(
            "Proposal must name the engine core-decrement routine; "
            "forecast math alone cannot remove the modifiers."
        )
    targets = [str(item) for item in (proposal.get("targets") or [])]
    for target in targets:
        if target in FORECAST_ONLY_ROUTINES:
            errors.append(
                f"Target {target} is forecast-only: func_1632 discards it, "
                "so editing it changes the screen, not the drain."
            )
        if target in SHARED_FIELDS:
            errors.append(
                f"Target {target} is shared with trinket/outfit benefits; "
                "zeroing it is not an isolated removal."
            )
    if proposal.get("changes_unrelated_rates") is True:
        errors.append(
            "Changing unrelated core rates does not meet the request."
        )
    unknowns = " ".join(
        str(item) for item in (proposal.get("open_unknowns") or [])
    ).lower()
    for owned in ("ownership", "cadence"):
        if owned not in unknowns:
            errors.append(
                f"Proposal must own the unproven {owned} as an open unknown."
            )
    return errors
