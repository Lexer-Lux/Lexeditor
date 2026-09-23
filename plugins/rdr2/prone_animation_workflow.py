"""Prone weapon-animation pipeline and pose workflow (#167).

Issue 167 exhausted the no-new-animation path: the one-handed grounded
aim loop runs but shots do not track the reticle, and no authored
face-down longarm, reload, or binocular set exists. What remains is
authored animation asset work plus visual QA: face-down one- and
two-handed draw/holster/idle/aim/fire/reload sets, reticle-driven
yaw/pitch aim poses, recoil and reload events, binocular raise/view/
lower, upper-body masks that preserve the prone lower body, correct
hand/weapon contacts, and zero unintended root motion. Vanilla clips
can be retargeted and modified, but arbitrary existing clips cannot be
played unchanged (reusing unchanged clips already failed its test).

This module records that workflow as checkable data and validates an
animation plan: clips must pass every pipeline stage (select/retarget,
export, rebuild, load, play, visual QA), prove one modified clip
end-to-end before a full set is generated, and meet the per-set pose,
event, mask, contact, and root-motion requirements. No gameplay claim:
the pipeline, the authored sets, and Lexer visual QA still need the
game and the art toolchain.
"""

from __future__ import annotations

from collections.abc import Mapping

# Pipeline stages in order; one modified clip must pass all of them
# before a full set is generated.
PIPELINE_STAGES = (
    "select_or_retarget_clip",
    "export",
    "rebuild",
    "load",
    "play",
    "visual_qa",
)

# Animation sets the issue discussion requires.
REQUIRED_SETS = (
    "one_handed_draw_holster_idle_aim_fire_reload",
    "two_handed_draw_holster_idle_aim_fire_reload",
    "binocular_raise_view_lower",
)

# Per-set requirements beyond the raw clips.
SET_REQUIREMENTS = (
    "reticle_driven_yaw_pitch_poses",
    "recoil_events",
    "reload_events",
    "upper_body_masks_preserve_prone_lower_body",
    "hand_weapon_contacts",
    "zero_unintended_root_motion",
)

# Approaches the issue discussion already rejected.
REJECTED_APPROACHES = (
    "play_unchanged_clip",
    "canned_clip_clears_tasks",
)


def pipeline_stages() -> list[str]:
    """Return the animation pipeline stages in order."""
    return list(PIPELINE_STAGES)


def validate_animation_plan(plan: Mapping) -> list[str]:
    """Check a prone-animation plan against the workflow contract."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["Animation plan must be a mapping."]
    approach = str(plan.get("approach", ""))
    for rejected in REJECTED_APPROACHES:
        if rejected in approach:
            errors.append(
                f"Approach {approach!r} reuses the rejected {rejected} "
                "position."
            )
    stages = plan.get("stages") or {}
    for required in PIPELINE_STAGES:
        if stages.get(required) is not True:
            errors.append(f"Pipeline must pass {required}.")
    if plan.get("single_clip_proven_first") is not True:
        errors.append(
            "One modified clip must export, rebuild, load, and play "
            "before a full set is generated."
        )
    sets = plan.get("sets") or {}
    for required in REQUIRED_SETS:
        record = sets.get(required) or {}
        if record.get("authored") is not True:
            errors.append(f"Animation set {required} must be authored.")
            continue
        for requirement in SET_REQUIREMENTS:
            if record.get(requirement) is not True:
                errors.append(
                    f"Set {required} must meet {requirement}."
                )
    return errors
