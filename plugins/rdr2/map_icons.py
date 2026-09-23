"""Map-icon design review contract (#138).

Issue 138 requires candidate map-icon designs to be shown, revised from
Lexer feedback, with existing artwork replaced only after approval.
Preparing and presenting the variants is the development task; approving
unseen artwork is never requested.

This module records that review flow as checkable data and validates a
review plan: variants must be presented first, feedback must be applied,
and replacement must wait for explicit approval. It rejects shipping
unapproved artwork and any claim that unseen art was approved. No art
claim: candidate variants and the approval session are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping

# Steps the review flow requires, in order.
REVIEW_STEPS = (
    "prepare_candidate_variants",
    "present_for_feedback",
    "revise_from_feedback",
    "explicit_approval",
    "replace_existing_artwork",
)

# Claims the issue discussion already rejected.
REJECTED_CLAIMS = (
    "approve_unseen_artwork",
    "ship_unapproved_artwork",
)


def review_steps() -> list[str]:
    """Return the required review steps in order."""
    return list(REVIEW_STEPS)


def validate_icon_review(plan: Mapping) -> list[str]:
    """Check a map-icon review plan against the required flow."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Icon review plan must be a mapping."]
    claim = str(plan.get("claim", ""))
    for rejected in REJECTED_CLAIMS:
        if rejected in claim:
            errors.append(f"Plan reuses the rejected claim {rejected}.")
    steps = plan.get("steps") or {}
    for required in REVIEW_STEPS:
        if steps.get(required) is not True:
            errors.append(f"Review flow must include {required}.")
    order = plan.get("step_order") or []
    if order and [s for s in order if s in REVIEW_STEPS] != [
        s for s in REVIEW_STEPS if s in order
    ]:
        errors.append("Review steps must run in the required order.")
    if steps.get("replace_existing_artwork") is True and steps.get(
        "explicit_approval"
    ) is not True:
        errors.append("Existing artwork must not be replaced before approval.")
    return errors


# Fields that make a candidate a reviewable variant brief. This defines
# what counts as presentable for the approval session, not the artwork
# itself: each brief names its subject, style axis, and sizes so Lexer
# feedback can target a concrete option.
VARIANT_BRIEF_FIELDS = (
    "subject",
    "style_axis",
    "sizes",
    "presentation_state",
)


def variant_brief_fields() -> list[str]:
    """Return the fields a reviewable variant brief must carry."""
    return list(VARIANT_BRIEF_FIELDS)


def validate_variant_brief(brief: Mapping) -> list[str]:
    """Check one candidate variant brief for review readiness."""
    errors: list[str] = []
    if not isinstance(brief, Mapping):
        return ["Variant brief must be a mapping."]
    for field in VARIANT_BRIEF_FIELDS:
        if not brief.get(field):
            errors.append(f"Variant brief must state {field}.")
    if brief.get("presentation_state") not in (
        "draft", "presented", "revised", "approved",
    ):
        errors.append(
            "Variant brief needs a real presentation state, "
            "not an approval claim for unseen artwork."
        )
    return errors
