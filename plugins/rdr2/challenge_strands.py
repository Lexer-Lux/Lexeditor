"""Challenge strand/rank extension contract (#231, #232).

Issue 231 needs additional challenge strands without pretending data
alone can extend the vanilla menu's nine links. Issue 232 needs serial
or parallel ranks that keep one visible strand and correct progress;
splitting ranks into separate roots produced duplicate menu entries and
progress/script problems and stays rejected.

This module records both boundaries as checkable data and validates a
strand plan: no data-only menu-link additions, no split-root duplicate
strands, one visible strand with correct progress, and ownership of the
runtime-interface approach plus its save/progress behavior as open
unknowns. No gameplay claim: the interface investigation, the Lexer
design decision and game-side proof are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping

# The vanilla challenge menu exposes nine strand links; data alone cannot
# add a tenth.
VANILLA_MENU_LINKS = 9

# Approaches the issue discussion already rejected.
REJECTED_APPROACHES = (
    "data_only_menu_link",
    "split_root_ranks",
)


def validate_strand_plan(plan: Mapping) -> list[str]:
    """Check a challenge strand/rank plan against both boundaries."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Strand plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected} path."
            )
    if not plan.get("interface"):
        errors.append(
            "Plan must name its runtime-interface approach; data alone "
            "cannot extend the nine-link vanilla menu."
        )
    strands = plan.get("visible_strands")
    if strands != 1:
        errors.append(
            "Plan must keep exactly one visible strand per challenge line."
        )
    if plan.get("progress_correct") is not True:
        errors.append(
            "Plan must keep correct progress; duplicate entries and "
            "script problems stay rejected."
        )
    unknowns = " ".join(str(item) for item in (plan.get("open_unknowns") or [])).lower()
    for owned in ("interface", "save", "progress"):
        if owned not in unknowns:
            errors.append(
                f"Plan must own the {owned} behavior as an open unknown."
            )
    return errors
