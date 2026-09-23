"""Hermetic checks for the issue-167 animation workflow contract (no game)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import prone_animation_workflow as paw


def authored_set():
    return {
        "authored": True,
        "reticle_driven_yaw_pitch_poses": True,
        "recoil_events": True,
        "reload_events": True,
        "upper_body_masks_preserve_prone_lower_body": True,
        "hand_weapon_contacts": True,
        "zero_unintended_root_motion": True,
    }


def valid_plan():
    return {
        "approach": "authored_retargeted_sets",
        "stages": {
            "select_or_retarget_clip": True,
            "export": True,
            "rebuild": True,
            "load": True,
            "play": True,
            "visual_qa": True,
        },
        "single_clip_proven_first": True,
        "sets": {
            "one_handed_draw_holster_idle_aim_fire_reload": authored_set(),
            "two_handed_draw_holster_idle_aim_fire_reload": authored_set(),
            "binocular_raise_view_lower": authored_set(),
        },
    }


class ProneAnimationWorkflowTests(unittest.TestCase):
    def test_stages_ordered(self):
        self.assertEqual(paw.pipeline_stages()[0], "select_or_retarget_clip")
        self.assertEqual(paw.pipeline_stages()[-1], "visual_qa")

    def test_valid_plan_passes(self):
        self.assertEqual(paw.validate_animation_plan(valid_plan()), [])

    def test_unchanged_clip_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "play_unchanged_clip prone"
        errors = paw.validate_animation_plan(plan)
        self.assertTrue(any("play_unchanged_clip" in e for e in errors))

    def test_full_set_before_single_clip_is_rejected(self):
        plan = valid_plan()
        plan["single_clip_proven_first"] = False
        errors = paw.validate_animation_plan(plan)
        self.assertTrue(any("single_clip_proven_first" in e or
                            "One modified clip" in e for e in errors))

    def test_missing_qa_stage_is_rejected(self):
        plan = valid_plan()
        plan["stages"]["visual_qa"] = False
        errors = paw.validate_animation_plan(plan)
        self.assertTrue(any("visual_qa" in e for e in errors))

    def test_missing_pose_requirement_is_rejected(self):
        plan = valid_plan()
        plan["sets"]["two_handed_draw_holster_idle_aim_fire_reload"][
            "reticle_driven_yaw_pitch_poses"] = False
        errors = paw.validate_animation_plan(plan)
        self.assertTrue(any("reticle_driven_yaw_pitch_poses" in e
                            for e in errors))

    def test_missing_root_motion_requirement_is_rejected(self):
        plan = valid_plan()
        plan["sets"]["binocular_raise_view_lower"][
            "zero_unintended_root_motion"] = False
        errors = paw.validate_animation_plan(plan)
        self.assertTrue(any("zero_unintended_root_motion" in e
                            for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(paw.validate_animation_plan("prone"))


if __name__ == "__main__":
    unittest.main()
