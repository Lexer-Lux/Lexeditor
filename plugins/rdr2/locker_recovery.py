"""Ordinary locker-list recovery for lost unique melee/throwables (#165).

Issue 165 requires lost unique hatchets/tomahawks to return through the
camp locker weapon list, unequipped and without duplication. The installed
named Recover action workaround does not meet that request, and the native
melee/throwable filter still has no safe solution.

This module records that boundary as checkable data and validates a
recovery-test plan: every step must return the exact weapon through the
ordinary locker list (not the Recover action alone), unequipped, with a
duplication check, and the plan must own the unresolved filter instead of
assuming it fixed. No gameplay claim: the filter solution and the game
session are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Lost-weapon cases evidenced in the issue discussion. The Viking Hatchet is
# the concrete reported loss (thrown into a tree, then absent from the camp
# locker); hatchets/tomahawks are the requested recovery classes.
KNOWN_LOST_CASES = (
    {
        "case": "VIKING_HATCHET",
        "label": "Viking Hatchet",
        "class": "unique hatchet",
        "evidence": "reported thrown into a tree, absent from camp locker",
    },
    {
        "case": "UNIQUE_HATCHET",
        "label": "Lost unique hatchet",
        "class": "unique hatchet",
        "evidence": "requested recovery class in the issue body",
    },
    {
        "case": "UNIQUE_TOMAHAWK",
        "label": "Lost unique tomahawk",
        "class": "unique tomahawk",
        "evidence": "requested recovery class in the issue body",
    },
)

# The only acceptance route: an ordinary entry in the camp locker weapon
# list. The named Recover action is the installed workaround, not the goal.
ACCEPTANCE_ROUTE = "locker_list"
WORKAROUND_ROUTE = "recover_action"

# Open unknowns a plan must own instead of assuming solved.
OPEN_UNKNOWNS = (
    "Safe solution to the native melee/throwable locker-list filter.",
)


def lost_cases() -> list[dict]:
    """Return an independent copy of the evidenced lost-weapon cases."""
    return copy.deepcopy([dict(case) for case in KNOWN_LOST_CASES])


def validate_recovery_plan(plan: Mapping) -> list[str]:
    """Check a locker-recovery test plan against the issue requirements."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Recovery plan must be a mapping with steps and open unknowns."]
    steps = plan.get("steps")
    if not steps:
        return ["Recovery plan must list at least one recovery step."]
    known = {case["case"] for case in KNOWN_LOST_CASES}
    for index, step in enumerate(steps):
        where = f"step {index + 1}"
        if not isinstance(step, Mapping):
            errors.append(f"{where} must be a mapping.")
            continue
        case = step.get("case")
        if case not in known:
            errors.append(
                f"{where} names unknown case {case!r}; "
                "use an evidenced lost-weapon case."
            )
        if step.get("route") != ACCEPTANCE_ROUTE:
            errors.append(
                f"{where} must return through the ordinary locker list "
                f"({ACCEPTANCE_ROUTE}); the named Recover action "
                f"({WORKAROUND_ROUTE}) alone does not meet the request."
            )
        if step.get("unequipped") is not True:
            errors.append(
                f"{where} must return the weapon unequipped."
            )
        if step.get("dedupe_check") is not True:
            errors.append(
                f"{where} must confirm the return without duplication."
            )
    unknowns = plan.get("open_unknowns") or []
    owned = " ".join(str(item) for item in unknowns).lower()
    if "filter" not in owned and "melee" not in owned:
        errors.append(
            "Plan must own the unresolved native melee/throwable filter "
            "as an open unknown instead of assuming it fixed."
        )
    return errors


# Acceptance criteria for the unresolved native melee/throwable
# locker-list filter. The filter is the #165 blocker: lost uniques must
# become visible as ordinary locker-list entries without dragging
# non-unique melee/throwables along, and the return stays unequipped and
# duplication-free.
FILTER_ACCEPTANCE_CRITERIA = (
    "lost_unique_visible_as_ordinary_locker_entry",
    "non_unique_melee_throwables_kept_out",
    "return_unequipped",
    "no_duplication_on_repeated_visits",
)


def filter_acceptance_criteria() -> list[str]:
    """Return the filter acceptance criteria."""
    return list(FILTER_ACCEPTANCE_CRITERIA)


def validate_locker_filter(plan: Mapping) -> list[str]:
    """Check a filter proposal against the locker-list acceptance criteria."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Filter plan must be a mapping."]
    if plan.get("assumes_filter_solved") is True:
        errors.append(
            "Filter plan must not assume the native filter solved; "
            "own it as the open unknown."
        )
    results = plan.get("results") or {}
    for required in FILTER_ACCEPTANCE_CRITERIA:
        if results.get(required) is not True:
            errors.append(
                f"Filter must prove {required}."
            )
    return errors

# Verdicts a completed recovery session may record per case.
RESULT_VERDICTS = ("pass", "fail")


def validate_session_result(result: Mapping) -> list[str]:
    """Check a completed locker-recovery session's per-case outcomes."""
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return ["Session result must be a mapping."]
    outcomes = result.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return ["Session result must list one outcome per lost-weapon case."]
    known = {case["case"] for case in KNOWN_LOST_CASES}
    for index, outcome in enumerate(outcomes):
        where = f"outcomes[{index}]"
        if not isinstance(outcome, Mapping):
            errors.append(f"{where} must be a mapping.")
            continue
        if outcome.get("case") not in known:
            errors.append(f"{where} must name an evidenced lost-weapon case.")
        if outcome.get("route") != ACCEPTANCE_ROUTE:
            errors.append(
                f"{where} must return through the ordinary locker list."
            )
        if outcome.get("verdict") not in RESULT_VERDICTS:
            errors.append(f"{where} needs a pass or fail verdict.")
        if outcome.get("verdict") == "pass":
            for field in ("unequipped", "no_duplication", "evidence"):
                if not outcome.get(field):
                    errors.append(f"{where} must record {field}.")
    return errors
