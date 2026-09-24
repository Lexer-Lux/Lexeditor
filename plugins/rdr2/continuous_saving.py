"""Reliable continuous-saving design contract (#121).

Issue 121 requires meaningful consequences to persist automatically while
removing normal manual-loading undo loops, with a development-only
recovery escape hatch. The concrete design lives in
docs/rdr2-continuous-saving-design.md: request/acknowledgement
sequencing over the game's own Story save owner (long_update func_110 /
func_501 / func_508 / func_1314 / func_506), consequence coverage for
death, arrest, checkpoints and crash recovery, and bounded storage.

This module records that design's acceptance checklist as checkable data
and validates a candidate plan against it. It rejects the known
insufficient substitutes from the design: periodic autosaving, a generic
"reapply inventory difference" replay rule, and save_menu_ui_event_handler
as an uncorrelated acknowledgement. No gameplay claim: the read-only
request/completion observer, idempotent consequence handling, and the
save-blocked-mission crash gap still need the game.
"""

from __future__ import annotations

from collections.abc import Mapping

# Checklist sections the design requires before any real-save candidate.
REQUIRED_SECTIONS = (
    "request_acknowledgement_sequencing",
    "consequence_coverage",
    "death_arrest_checkpoint_handling",
    "crash_recovery",
    "development_only_recovery_hatch",
    "bounded_storage",
)

# Consequence rows the design's table requires a commit boundary for.
REQUIRED_CONSEQUENCES = (
    "buy_sell_craft_consume",
    "crime_bounty_honor_reward",
    "death",
    "arrest",
    "mission_checkpoint_retry",
    "user_exit",
    "crash_or_forced_termination",
)

# Substitutes the design explicitly rejects.
REJECTED_SUBSTITUTES = (
    "periodic_autosave_only",
    "generic_inventory_difference_replay",
    "uncorrelated_save_complete_event",
)


def required_sections() -> list[str]:
    """Return the required design checklist sections."""
    return list(REQUIRED_SECTIONS)


def required_consequences() -> list[str]:
    """Return the consequence rows that need a commit boundary."""
    return list(REQUIRED_CONSEQUENCES)


def validate_saving_plan(plan: Mapping) -> list[str]:
    """Check a continuous-saving candidate plan against the design."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Saving plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_SUBSTITUTES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected} substitute."
            )
    sections = plan.get("sections") or {}
    for required in REQUIRED_SECTIONS:
        if sections.get(required) is not True:
            errors.append(f"Plan must cover design section {required}.")
    consequences = plan.get("consequences") or {}
    for required in REQUIRED_CONSEQUENCES:
        if consequences.get(required) != "commit_boundary_defined":
            errors.append(
                f"Consequence {required} needs a defined commit boundary."
            )
    if plan.get("mutates_real_saves") is True and not plan.get("design_approved"):
        errors.append(
            "Real saves must not be touched before the design is approved."
        )
    return errors

# Fields every observed save request/completion pair must carry. The
# observer is read-only: it correlates the game's own completions with
# their requests by sequence number and never mutates a save.
OBSERVER_PAIR_FIELDS = ("sequence", "request", "completion")


def validate_observer_report(report: Mapping) -> list[str]:
    """Check a read-only save request/completion observer report."""
    errors: list[str] = []
    if not isinstance(report, Mapping):
        return ["Observer report must be a mapping."]
    if report.get("read_only") is not True:
        errors.append("The observer must be read-only; it mutates no save.")
    pairs = report.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        return ["Observer report must list at least one request/completion pair."]
    seen: set = set()
    for index, pair in enumerate(pairs):
        where = f"pairs[{index}]"
        if not isinstance(pair, Mapping):
            errors.append(f"{where} must be a mapping.")
            continue
        for field in OBSERVER_PAIR_FIELDS:
            if pair.get(field) in (None, ""):
                errors.append(f"{where} must carry {field}.")
        sequence = pair.get("sequence")
        if sequence in seen:
            errors.append(
                f"{where} reuses sequence {sequence!r}; completions must "
                "correlate one-to-one."
            )
        seen.add(sequence)
        if pair.get("correlated") is not True:
            errors.append(
                f"{where} must correlate its completion with its request; "
                "an uncorrelated SAVE_COMPLETE proves nothing."
            )
    return errors
